#!@python3@/bin/python3 -B
#
# refind-install.py — extended nixpkgs rEFInd installer.
# Base: nixpkgs/nixos/modules/system/boot/loader/refind/refind-install.py
# Extensions: theme deployment, dont_scan_dirs, #452075 fix, #453812 fix, orphan scan.

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import datetime
import json
from ctypes import CDLL
import os
import psutil
import re
import shutil
import subprocess
import sys
import textwrap


refind_dir = None
libc = CDLL("libc.so.6")
install_config = json.load(open('@configPath@', 'r'))


def config(*path: str) -> Optional[Any]:
    result = install_config
    for component in path:
        result = result[component]
    return result


def get_system_path(profile: str = 'system', gen: Optional[str] = None, spec: Optional[str] = None) -> str:
    basename = f'{profile}-{gen}-link' if gen is not None else profile
    profiles_dir = '/nix/var/nix/profiles'
    if profile == 'system':
        result = os.path.join(profiles_dir, basename)
    else:
        result = os.path.join(profiles_dir, 'system-profiles', basename)

    if spec is not None:
        result = os.path.join(result, 'specialisation', spec)

    return result


def get_profiles() -> List[str]:
    profiles_dir = '/nix/var/nix/profiles/system-profiles/'
    dirs = os.listdir(profiles_dir) if os.path.isdir(profiles_dir) else []

    return [path for path in dirs if not path.endswith('-link')]


def get_gens(profile: str = 'system') -> List[int]:
    nix_env = os.path.join(config('nixPath'), 'bin', 'nix-env')
    output = subprocess.check_output([
        nix_env, '--list-generations',
        '-p', get_system_path(profile),
        '--option', 'build-users-group', '',
    ], universal_newlines=True)

    gen_lines = output.splitlines()
    gen_nums = [int(line.split()[0]) for line in gen_lines]

    max_gens = config('maxGenerations')
    if max_gens > 0:
        return gen_nums[-max_gens:]
    return gen_nums


def is_encrypted(device: str) -> bool:
    for name, _ in config('luksDevices'):
        if os.readlink(os.path.join('/dev/mapper', name)) == os.readlink(device):
            return True

    return False


def is_fs_type_supported(fs_type: str) -> bool:
    return fs_type.startswith('vfat')


paths = {}

def get_copied_path_uri(path: str, target: str) -> str:
    package_id = os.path.basename(os.path.dirname(path))
    suffix = os.path.basename(path)
    dest_file = f'{package_id}-{suffix}'
    dest_path = os.path.join(refind_dir, target, dest_file)

    if not os.path.exists(dest_path):
        copy_file(path, dest_path)
    else:
        paths[dest_path] = True

    return os.path.join('/efi/refind', target, dest_file)

def get_path_uri(path: str) -> str:
    return get_copied_path_uri(path, "")


def get_file_uri(profile: str, gen: Optional[str], spec: Optional[str], name: str) -> str:
    gen_path = get_system_path(profile, gen, spec)
    path_in_store = os.path.realpath(os.path.join(gen_path, name))
    return get_path_uri(path_in_store)


def get_kernel_uri(kernel_path: str) -> str:
    return get_copied_path_uri(kernel_path, "kernels")


@dataclass
class BootSpec:
    system: str
    init: str
    kernel: str
    kernelParams: List[str]
    label: str
    toplevel: str
    specialisations: Dict[str, "BootSpec"]
    initrd: str | None = None
    initrdSecrets: str | None = None


def bootjson_to_bootspec(bootjson: dict) -> BootSpec:
    specialisations = bootjson.get('org.nixos.specialisation.v1', {})
    specialisations = {k: bootjson_to_bootspec(v) for k, v in specialisations.items()}
    return BootSpec(
        **bootjson['org.nixos.bootspec.v1'],
        specialisations=specialisations,
    )


def config_entry(is_sub: bool, bootspec: BootSpec, label: str, time: str, is_latest: bool) -> str:
    entry = ""
    if is_sub:
        entry += 'sub'

    entry += f'menuentry "{label}" {{\n'

    icon_path = "themes/rEFInd-glassy/icons/"
    icon_file = "os_nixos.png" if is_latest else "os_nixos_gray.png"
    entry += f'  icon {icon_path}{icon_file}\n'
    
    entry += '  loader ' + get_kernel_uri(bootspec.kernel) + '\n'

    if bootspec.initrd:
        entry += '  initrd ' + get_kernel_uri(bootspec.initrd) + '\n'

    entry += '  options "' + ' '.join(['init=' + bootspec.init] + bootspec.kernelParams).strip() + '"\n'
    entry += '}\n'
    return entry


def generate_config_entry(profile: str, gen: int, special: bool, group_name: str, is_latest: bool) -> str:
    time = datetime.datetime.fromtimestamp(os.stat(get_system_path(profile, gen), follow_symlinks=False).st_mtime).strftime("%F %H:%M:%S")
    boot_json_path = os.path.join(get_system_path(profile, gen), 'boot.json')

    if not os.path.exists(boot_json_path):
        print(f"warning: generation {gen} has no boot.json, skipping")
        return ""

    boot_json = json.load(open(boot_json_path, 'r'))
    boot_spec = bootjson_to_bootspec(boot_json)

    specialisation_list = boot_spec.specialisations.items()
    entry = ""

    if len(specialisation_list) > 0:
        entry += f'menuentry "NixOS {group_name} Generation {gen}" {{\n'
        entry += config_entry(True, boot_spec, f'Default', str(time), is_latest)

        for spec, spec_boot_spec in specialisation_list:
            entry += config_entry(True, spec_boot_spec, f'{spec}', str(time), is_latest)

        entry += '}\n'
    else:
        entry += config_entry(False, boot_spec, f'NixOS {group_name} Generation {gen}', str(time), is_latest)
    return entry


def find_disk_device(part: str) -> str:
    part = os.path.realpath(part)
    part = part.removeprefix('/dev/')
    disk = os.path.realpath(os.path.join('/sys', 'class', 'block', part))
    disk = os.path.dirname(disk)

    return os.path.join('/dev', os.path.basename(disk))


def find_mounted_device(path: str) -> str:
    path = os.path.abspath(path)

    while not os.path.ismount(path):
        path = os.path.dirname(path)

    devices = [x for x in psutil.disk_partitions() if x.mountpoint == path]

    assert len(devices) == 1
    return devices[0].device


def copy_file(from_path: str, to_path: str):
    dirname = os.path.dirname(to_path)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    shutil.copyfile(from_path, to_path + ".tmp")
    fd = os.open(to_path + ".tmp", os.O_RDONLY)
    os.fsync(fd)
    os.close(fd)
    os.rename(to_path + ".tmp", to_path)

    paths[to_path] = True


def install_theme(theme_store_path: str) -> None:
    themes_dir = os.path.join(refind_dir, 'themes')
    active_dir = os.path.join(themes_dir, 'rEFInd-glassy')
    active_new = os.path.join(themes_dir, 'active.new')

    if not os.path.exists(themes_dir):
        os.makedirs(themes_dir)

    if os.path.exists(active_new):
        shutil.rmtree(active_new)

    shutil.copytree(theme_store_path, active_new)

    for dirpath, _, filenames in os.walk(active_new):
        for f in filenames:
            paths[os.path.join(dirpath, f)] = True

    if os.path.exists(active_dir):
        shutil.rmtree(active_dir)

    os.rename(active_new, active_dir)

    for dirpath, _, filenames in os.walk(active_dir):
        for f in filenames:
            full = os.path.join(dirpath, f)
            paths[full] = True


def install_bootloader() -> None:
    global refind_dir

    efi_mount = str(config('efiMountPoint'))
    if not os.path.ismount(efi_mount):
        raise RuntimeError(f"ESP not mounted at {efi_mount}")

    # FIX #452075: use same base dir for both efiRemovable and normal mode
    if config('efiRemovable'):
        refind_dir = os.path.join(efi_mount, 'efi', 'boot')
    else:
        refind_dir = os.path.join(efi_mount, 'efi', 'refind')

    if not os.path.exists(refind_dir):
        os.makedirs(refind_dir)
    else:
        for dir, dirs, files in os.walk(refind_dir, topdown=True):
            for file in files:
                paths[os.path.join(dir, file)] = False

    # Also track kernels dir
    kernels_dir = os.path.join(refind_dir, 'kernels')
    if os.path.exists(kernels_dir):
        for dir, dirs, files in os.walk(kernels_dir, topdown=True):
            for file in files:
                paths[os.path.join(dir, file)] = False

    profiles = [('system', get_gens())]

    for (profile, gens) in profiles:
        group_name = 'default profile' if profile == 'system' else f"profile '{profile}'"

        # Use enumerate to track the index
        for i, gen in enumerate(sorted(gens, key=lambda x: x, reverse=True)):
            is_latest = (i == 0)
            config_file += generate_config_entry(profile, gen, True, group_name, is_latest)

    timeout = config('timeout')

    # Install theme before generating config
    theme = config('theme')
    if theme:
        install_theme(theme)

    # Build config file
    extra_config = str(config('extraConfig')).strip()

    config_file = f'timeout {timeout}\n'

    banner_scale = config('bannerScale')
    if banner_scale:
        config_file += f'banner_scale {banner_scale}\n'

    text_only = config('textOnly')
    if text_only:
        config_file += 'textonly true\n'

    hide_ui = config('hideUI')
    if hide_ui:
        config_file += f'hideui {",".join(hide_ui)}\n'

    show_tools = config('showTools')
    if show_tools:
        config_file += f'showtools {",".join(show_tools)}\n'

    # Prevent duplicate entries from auto-scanner
    config_file += 'dont_scan_dirs EFI/nixos,efi/refind/kernels\n'

    # FIX #453812: only write default_selection if explicitly set
    default_selection = config('defaultSelection')
    if default_selection:
        config_file += f'default_selection {default_selection}\n'

    # Theme include — after all options so theme.conf can set visual defaults
    if theme:
        config_file += '\ninclude themes/rEFInd-glassy/theme.conf\n'

    config_file += '\n# NixOS boot entries start here\n'

    for (profile, gens) in profiles:
        group_name = 'default profile' if profile == 'system' else f"profile '{profile}'"

        for gen in sorted(gens, key=lambda x: x, reverse=True):
            config_file += generate_config_entry(profile, gen, True, group_name)

    config_file += '\n# NixOS boot entries end here\n'

    if extra_config:
        config_file += '\n\n' + extra_config

    config_file_path = os.path.join(refind_dir, 'refind.conf')

    with open(f"{config_file_path}.tmp", 'w') as file:
        file.truncate()
        file.write(config_file.strip())
        file.flush()
        os.fsync(file.fileno())
    os.rename(f"{config_file_path}.tmp", config_file_path)

    paths[config_file_path] = True

    for dest_path, source_path in config('additionalFiles').items():
        dest_path = os.path.join(refind_dir, dest_path)
        copy_file(source_path, dest_path)

    cpu_family = config('hostArchitecture', 'family')
    if cpu_family == 'x86':
        if config('hostArchitecture', 'bits') == 32:
            boot_file = 'BOOTIA32.EFI'
            efi_file = 'refind_ia32.efi'
        elif config('hostArchitecture', 'bits') == 64:
            boot_file = 'BOOTX64.EFI'
            efi_file = 'refind_x64.efi'
    elif cpu_family == 'arm':
        if config('hostArchitecture', 'arch') == 'armv8-a' and config('hostArchitecture', 'bits') == 64:
            boot_file = 'BOOTAA64.EFI'
            efi_file = 'refind_aa64.efi'
        else:
            raise Exception(f'Unsupported CPU arch: {config("hostArchitecture", "arch")}')
    else:
        raise Exception(f'Unsupported CPU family: {cpu_family}')

    efi_path = os.path.join(config('refindPath'), 'share', 'refind', efi_file)
    # FIX #452075: EFI binary goes in same dir as config
    dest_path = os.path.join(refind_dir, boot_file if config('efiRemovable') else efi_file)

    copy_file(efi_path, dest_path)

    if not config('efiRemovable') and not config('canTouchEfiVariables'):
        print('warning: canTouchEfiVariables is false and efiInstallAsRemovable is false.\n  The system may be unbootable without a NVRAM entry or fallback bootloader.', file=sys.stderr)

    if config('canTouchEfiVariables'):
        if config('efiRemovable'):
            print('note: efiInstallAsRemovable is true, no need to add EFI NVRAM entry.')
        else:
            efibootmgr = os.path.join(str(config('efiBootMgrPath')), 'bin', 'efibootmgr')
            efi_partition = find_mounted_device(str(config('efiMountPoint')))
            efi_disk = find_disk_device(efi_partition)

            try:
                efibootmgr_output = subprocess.check_output([efibootmgr], stderr=subprocess.STDOUT, universal_newlines=True)
            except subprocess.CalledProcessError as e:
                print(f'error: efibootmgr failed: {e.output}\n  Consider setting efiInstallAsRemovable = true', file=sys.stderr)
                raise

            refind_boot_entry = None
            if matches := re.findall(r'Boot([0-9a-fA-F]{4})\*? rEFInd', efibootmgr_output):
                refind_boot_entry = matches[0]

            if refind_boot_entry:
                boot_order = re.findall(r'BootOrder: ((?:[0-9a-fA-F]{4},?)*)', efibootmgr_output)[0]

                subprocess.check_output([
                    efibootmgr,
                    '-b', refind_boot_entry,
                    '-B',
                ], stderr=subprocess.STDOUT, universal_newlines=True)

                subprocess.check_output([
                    efibootmgr,
                    '-c',
                    '-b', refind_boot_entry,
                    '-d', efi_disk,
                    '-p', efi_partition.removeprefix(efi_disk).removeprefix('p'),
                    '-l', f'\\efi\\refind\\{efi_file}',
                    '-L', 'rEFInd',
                    '-o', boot_order,
                ], stderr=subprocess.STDOUT, universal_newlines=True)
            else:
                subprocess.check_output([
                    efibootmgr,
                    '-c',
                    '-d', efi_disk,
                    '-p', efi_partition.removeprefix(efi_disk).removeprefix('p'),
                    '-l', f'\\efi\\refind\\{efi_file}',
                    '-L', 'rEFInd',
                ], stderr=subprocess.STDOUT, universal_newlines=True)

    print("removing unused boot files...")
    for path in list(paths.keys()):
        if not paths[path]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    # Scan for orphaned files not in tracking dict
    for dirpath, _, filenames in os.walk(refind_dir):
        for f in filenames:
            full = os.path.join(dirpath, f)
            if full not in paths and not f.startswith('.'):
                print(f"removing orphaned file: {full}")
                os.remove(full)


def main() -> None:
    try:
        install_bootloader()
    finally:
        rc = libc.syncfs(os.open(f"{config('efiMountPoint')}", os.O_RDONLY))
        if rc != 0:
            print(f"could not sync {config('efiMountPoint')}: {os.strerror(rc)}", file=sys.stderr)

if __name__ == '__main__':
    main()
