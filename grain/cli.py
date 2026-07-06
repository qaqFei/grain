import typing
import pathlib
import json

import grain
import grain.config
import grain.package
import grain.storage
import grain.utils
import grain.local
import grain.build
from grain.logger import Logger

def list_find[T](lst: list[T], it: T, start: int = 0):
    try:
        return lst.index(it, start)
    except ValueError:
        return -1

def print_grain_info():
    config_path = grain.config.get_config_path()
    config = grain.config.Config.from_default()
    config.auto_compiler()
    config.auto_git()
    
    print(f"Grain version: {grain.__version__}")
    print(f"Current platform: {grain.utils.get_current_platform()}")
    print(f"Config path: {grain.config.get_config_path()}")
    print(f"Data directory: {config.data_dir}")
    print(f"Git: {config.git}")
    print(f"Compiler g++: {config.compiler_gpp}")
    print(f"Storage repo dir: {config.storage_repo_dir}")
    
    config.save(config_path)

def new_package(package_type: typing.Literal["lib", "app"], package_name: typing.Optional[str], pwd: typing.Optional[str] = None):
    if package_name is None:
        Logger.error("No package name specified")
        return
    
    if not grain.package.check_package_name(package_name):
        Logger.error("Invalid package name")
        return
    
    pkg_dir = pathlib.Path(package_name if pwd is None else (pwd / package_name)).resolve()
    
    if pkg_dir.exists():
        Logger.error(f"{pkg_dir} already exists")
        return
    
    Logger.info(f"Creating new package ({package_type}): {pkg_dir}")
    pkg_dir.mkdir(parents=True)
    
    if package_type == "lib":
        info = grain.package.LibraryInfo()
        info.namespace = package_name
    elif package_type == "app":
        info = grain.package.ApplicationInfo()
        info.name = package_name
    else: assert False
    
    with open(grain.package.get_package_info_path(pkg_dir), "w", encoding="utf-8") as f:
        json.dump(info.dump(), f, **grain.utils.jdump_args())
    
    (pkg_dir / grain.package.get_source_filename(info)).write_text(grain.package.get_default_source(info), encoding="utf-8")
        
def init_storage():
    config = grain.config.Config.from_default().check_git()
    grain.storage.init_repo(config.storage_repo_as_path(), config.git)

def set_storage_remote(remote: typing.Optional[str]):
    if remote is None:
        Logger.error("No remote specified")
        return
    
    config = grain.config.Config.from_default().check_git()
    grain.storage.set_remote(config.storage_repo_as_path(), config.git, remote)

def push_storage():
    config = grain.config.Config.from_default().check_git()
    grain.storage.push_repo(config.storage_repo_as_path(), config.git, "by cli (grain storage push)")

def package_draft_release(pkg_dir: typing.Optional[str]):
    if pkg_dir is None: pkg_dir = "."
    
    pkg_dir = pathlib.Path(pkg_dir).resolve()
    Logger.info(f"Drafting release for package: {pkg_dir}")
    
    config = grain.config.Config.from_default().check_git()
    grain.storage.draft_release(config.storage_repo_as_path(), config.git, pkg_dir)

def ensure_package(name: typing.Optional[str], version: typing.Optional[str]):
    if name is None:
        Logger.error("No package name specified")
        return

    if version is None:
        Logger.error("No package version specified")
        return
    
    version = int(version)
    
    config = grain.config.Config.from_default()
    grain.local.ensure_package(config.storage_repo_as_path(), config.data_dir_as_path(), name, version)

def build_package(pkg_dir: typing.Optional[str], argv: list[str], configurer: typing.Optional[typing.Callable[[grain.build.BuildConfig], None]] = None):
    if pkg_dir is None: pkg_dir = "."
    
    pkg_dir = pathlib.Path(pkg_dir).resolve()
    Logger.info(f"Building for package: {pkg_dir}")
    
    config = grain.config.Config.from_default()
    build_to = config.ensure_default_build_path() / "main"
    
    if "--out" in argv:
        build_to = pathlib.Path(argv[argv.index("--out") + 1]).resolve()
    
    build_config = grain.build.BuildConfig(output=str(build_to))
    del build_to
    
    if "--release" in argv: build_config.is_release = True
    if "--run" in argv: build_config.run_immediately = True
    
    macro_i = list_find(argv, "--macro")
    while macro_i != -1:
        build_config.macros.append(argv[macro_i + 1])
        macro_i = list_find(argv, "--macro", macro_i + 2)
    
    if configurer is not None: configurer(build_config)
    
    grain.build.build(config, pkg_dir, build_config)

def clean_local_packages():
    config = grain.config.Config.from_default()
    grain.local.clean_packages(config.data_dir_as_path())

def find_package(sub: typing.Optional[str]):
    if sub is None:
        Logger.error("No sub name specified")
        return

    config = grain.config.Config.from_default()
    
    for name, ver in grain.storage.get_all_packages(config.storage_repo_as_path()):
        if sub in name:
            print(f"{name} {ver}")

def add_external_package(name: typing.Optional[str], pkg_dir: typing.Optional[str], *, given: typing.Optional[tuple[str, int]] = None):
    if name is None:
        Logger.error("No package name specified")
        return
    
    if pkg_dir is None: pkg_dir = "."
    pkg_dir = pathlib.Path(pkg_dir).resolve()
    
    config = grain.config.Config.from_default()
    info = grain.package.load_package_info(pkg_dir)
    
    if given is None:
        for packname, _ in grain.storage.get_all_packages(config.storage_repo_as_path()):
            if packname == name:
                version = grain.storage.get_latest_package_version(config.storage_repo_as_path(), name)
                break
        else:
            Logger.error(f"Package {name} not found")
            return
    else:
        packname, version = given
    
    info.requirements.externals.get().append(f"{packname}=={version}")
    
    with open(grain.package.get_package_info_path(pkg_dir), "w", encoding="utf-8") as f:
        json.dump(info.dump(), f, **grain.utils.jdump_args())
        
    Logger.info(f"Added external package: {name}=={version}")

def add_test_for_package(pkg_dir: typing.Optional[str]):
    if pkg_dir is None: pkg_dir = "."
    pkg_dir = pathlib.Path(pkg_dir).resolve()
    
    if (pkg_dir / "files" / "test").exists():
        Logger.error("Test package already exists")
        return
    
    name = grain.package.get_name_from_package(pkg_dir)
    
    new_package("app", "test", pkg_dir / "files")
    add_external_package(name, pkg_dir / "files" / "test", given=(name, 0))

def run_test_for_package(pkg_dir: typing.Optional[str], argv: list[str]):
    if pkg_dir is None: pkg_dir = "."
    pkg_dir = pathlib.Path(pkg_dir).resolve()
    
    def configurer(config: grain.build.BuildConfig):
        config.run_immediately = True
        config.externals.append(pkg_dir)
    
    build_package(pkg_dir / "files" / "test", argv, configurer)

def main():
    import sys
    argv = sys.argv.copy()
    argv_index = 1
    
    def next_argv():
        nonlocal argv_index
        
        if argv_index >= len(argv): return None
        result = argv[argv_index]
        argv_index += 1
        return result

    def curr_argv():
        if argv_index - 1 >= len(argv): return None
        return argv[argv_index - 1]

    match next_argv():
        case "info": print_grain_info()
        
        case "package":
            match next_argv():
                case "new":
                    match next_argv():
                        case "lib" | "app": new_package(curr_argv(), next_argv())
                        case None: print("No package type specified")
                        case _: print("Unknown package type")
                        
                case "draft-release": package_draft_release(next_argv())
                case "ensure": ensure_package(next_argv(), next_argv())
                case "build": build_package(next_argv(), sys.argv)
                case "clean": clean_local_packages()
                case "find": find_package(next_argv())
                case "add-external": add_external_package(next_argv(), next_argv())
                case "add-test": add_test_for_package(next_argv())
                case "run-test": run_test_for_package(next_argv(), sys.argv)
                case None: print("No command specified")
                case _: print("Unknown command")
        
        case "storage":
            match next_argv():
                case "init": init_storage()
                case "set-remote": set_storage_remote(next_argv())
                case "push": push_storage()
                case None: print("No command specified")
                case _: print("Unknown command")
        
        case None: print("No command specified")
        case _: print("Unknown command")
