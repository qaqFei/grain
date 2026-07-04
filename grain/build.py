import pathlib
import dataclasses
import subprocess

import grain.package
import grain.config
import grain.utils
import grain.local
from grain.logger import Logger

@dataclasses.dataclass
class FinalSource:
    code: str
    includes: list[str]
    links: list[str]
    platform_links: list[str]

@dataclasses.dataclass
class BuildConfig:
    output: str
    is_release: bool = False
    run_immediately: bool = False
    externals: list[pathlib.Path] = dataclasses.field(default_factory=list)

def generate_final_source(repo: pathlib.Path, data_dir: pathlib.Path, pkg_dir: pathlib.Path, build_config: BuildConfig):
    std_includes = set()
    platform_links = set()
    processed_packages = set()
    final_code = []
    final_includes = []
    final_links = []
    
    def trans_namespace(name: str, ver: int):
        return f"{name}_{ver}"
    
    def process(pkg_dir: pathlib.Path, is_app: bool = False):
        info = grain.package.load_package_info(pkg_dir)
        std_includes.update(info.requirements.standards.get())
        externals = info.requirements.externals.get()
        
        if is_app and isinstance(info, grain.package.LibraryInfo):
            raise Exception("Cannot build a single library as an application")
        
        if not is_app and isinstance(info, grain.package.ApplicationInfo):
            raise Exception("Cannot build an application as a library")
        
        version = grain.local.get_version(pkg_dir)
        is_local = version is None
        if is_local: version = 0
        
        for i in externals:
            if i in processed_packages: continue
            sub = grain.local.ensure_package(repo, data_dir, *grain.utils.parse_package_name(i))
            process(sub)
            
        for name, ver in map(grain.utils.parse_package_name, externals):
            final_code.append(f"#define {name} {trans_namespace(name, ver)}")
        
        if isinstance(info, grain.package.LibraryInfo):
            final_code.append(f"#define {info.namespace} {trans_namespace(info.namespace, version)}")
        
        raw_source_path = pkg_dir / grain.package.get_source_filename(info)
        final_code.append(raw_source_path.read_text(encoding="utf-8"))
        
        for name, _ in map(grain.utils.parse_package_name, externals):
            final_code.append(f"#undef {name}")
        
        if isinstance(info, grain.package.LibraryInfo):
            final_code.append(f"#undef {info.namespace}")
        
        if not is_app:
            if not is_local:
                final_includes.append(str(pkg_dir / ".grain" / "includes"))
                
                for lib in (pkg_dir / ".grain" / "libs").iterdir():
                    final_links.append(str(lib))
            else:
                grain.local.copy_includes_to(info, pkg_dir, pkg_dir / ".grain" / "includes" / info.namespace)
                final_includes.append(str(pkg_dir / ".grain" / "includes"))
                
                for file in info.exports.libs.get():
                    file = grain.package.get_path_relative_to_package(pkg_dir, file)
                    final_links.append(str(file))
            
        if isinstance(info, grain.package.LibraryInfo):
            processed_packages.add(f"{info.namespace}=={version}")
        
        platform_links.update(info.requirements.platform_links.get())
    
    for i in build_config.externals: process(i)
    process(pkg_dir, is_app=True)
    
    final_code[:0] = map(lambda x: f"#include <{x}>", std_includes)
    
    final_code.append("""
int main() {
    entrypoint();
    return 0;
}
""")

    return FinalSource("\n".join(final_code), final_includes, final_links, list(platform_links))

def generate_build_command(config: grain.config.Config, final_source: FinalSource, build_config: BuildConfig):
    source_path = config.ensure_default_build_path() / "source.cpp"
    source_path.write_text(final_source.code, encoding="utf-8")
    
    result = [
        config.compiler_gpp,
        "-std=c++20", "-static",
        "-Os" if build_config.is_release else "-O0",
        "" if build_config.is_release else "-ggdb",
        "-ffunction-sections" if build_config.is_release else "",
        "-fdata-sections" if build_config.is_release else "",
        "-Wsign-compare",
        "-Wa,-mbig-obj",
        "-DGRAIN_IS_RELEASE" if build_config.is_release else "",
        *map(lambda x: f"-I{x}", final_source.includes),
        str(source_path),
        *final_source.links,
        *map(lambda x: f"-l{x}", final_source.platform_links),
        "-Wl,--gc-sections" if build_config.is_release else "",
        "-o", build_config.output,
    ]
    
    return list(filter(bool, result))

def build(config: grain.config.Config, app_dir: pathlib.Path, build_config: BuildConfig):
    final_source = generate_final_source(config.storage_repo_as_path(), config.data_dir_as_path(), app_dir, build_config)
    command = generate_build_command(config, final_source, build_config)
    Logger.info("Building application:", command)
    
    pro = subprocess.run(command)
    pro.check_returncode()
    
    if build_config.run_immediately:
        subprocess.run([build_config.output])
