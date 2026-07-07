import pathlib
import dataclasses
import subprocess
import json
import zipfile
import uuid

from ordered_set import OrderedSet

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
    is_app: bool

@dataclasses.dataclass
class BuildConfig:
    output: str
    is_release: bool = False
    run_immediately: bool = False
    externals: list[pathlib.Path] = dataclasses.field(default_factory=list)
    macros: list[str] = dataclasses.field(default_factory=list)

def parse_macro(macro: str):
    eqi = macro.find("=")
    if eqi == -1: return macro, None
    return macro[:eqi], macro[eqi+1:]

def generate_final_source(repo: pathlib.Path|str, data_dir: pathlib.Path, pkg_dir: pathlib.Path, build_config: BuildConfig):
    std_includes = OrderedSet()
    platform_links = OrderedSet()
    processed_packages = set()
    final_code = []
    final_includes = []
    final_links = []
    embed_files = {}
    
    for name, value in map(parse_macro, build_config.macros):
        if value is None: final_code.append(f"#define {name}")
        else: final_code.append(f"#define {name} {value}")
    
    if build_config.is_release:
        final_code.append("#define GRAIN_IS_RELEASE")
    
    final_code.append("""
static int _grain_argc;
static char** _grain_argv;

namespace grain {
    void* get_embed_file(const char* name, int* size);
    
    void get_args(int* argc, char*** argv) {
        *argc = _grain_argc;
        *argv = _grain_argv;
    }
}
""")
    
    def trans_namespace(name: str, ver: int):
        return f"{name}_{ver}"
    
    def process(pkg_dir: pathlib.Path):
        info = grain.package.load_package_info(pkg_dir)
        std_includes.update(info.requirements.standards.get())
        externals = info.requirements.externals.get()
        pkg_name = grain.package.get_name_from_info(info)
        
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
        
        if isinstance(info, grain.package.LibraryInfo):
            links = []
            
            if not is_local:
                final_includes.append(str(pkg_dir / ".grain" / "includes"))
                
                libs_dir = pkg_dir / ".grain" / "libs"
                
                with open(libs_dir / "catalog.json", "r", encoding="utf-8") as f:
                    libs_catalog: list[str] = json.load(f)
                
                for lib in libs_catalog:
                    links.append(str(libs_dir / lib))
            else:
                grain.local.copy_includes_to(info, pkg_dir, pkg_dir / ".grain" / "includes" / info.namespace)
                final_includes.append(str(pkg_dir / ".grain" / "includes"))
                
                for file in info.exports.libs.get():
                    file = grain.package.get_path_relative_to_package(pkg_dir, file)
                    links.append(str(file))
            
            links.reverse()
            final_links.extend(links)
            
        if isinstance(info, grain.package.LibraryInfo):
            processed_packages.add(f"{info.namespace}=={version}")
        
        platform_links.update(info.requirements.platform_links.get())
        
        if not is_local:
            embeds_dir = pkg_dir / ".grain" / "embeds"
            
            if embeds_dir.exists():
                with open(embeds_dir / "catalog.json", "r", encoding="utf-8") as f:
                    embeds_catalog: dict[str, str] = json.load(f)
                
                for key, value in embeds_catalog.items():
                    embed_files[f"{pkg_name}/{key}"] = embeds_dir / value
        else:
            for key, file in info.requirements.embeds.items():
                embed_files[f"{pkg_name}/{key}"] = grain.package.get_path_relative_to_package(pkg_dir, file)
        
        return info, version
    
    for i in build_config.externals: process(i)
    info, version = process(pkg_dir)
    
    if isinstance(info, grain.package.LibraryInfo):
        final_code.append(f"#define {info.namespace} {trans_namespace(info.namespace, version)}")
    
    final_code[:0] = map(lambda x: f"#include <{x}>", std_includes)
    
    embed_keys_bucket = {}
    def get_embed_varname(key: str):
        if key not in embed_keys_bucket:
            embed_keys_bucket[key] = len(embed_keys_bucket)
            
        id = embed_keys_bucket[key]
        return f"_grain_embed_{id}"
    
    for key, file in embed_files.items():
        with open(file, "rb") as f:
            data = f.read()
            
        final_code.append(f"static const unsigned char {get_embed_varname(key)}[] = {{{",".join(map(str, data))}}};")
    
    final_code.append(f"""
void* grain::get_embed_file(const char* name, int* size) {{
    {"\n".join(map(lambda key, index: f"""
{"if" if index == 0 else "else if"} (strcmp(name, "{key}") == 0) {{
    *size = sizeof({get_embed_varname(key)});
    return (void*)(&{get_embed_varname(key)}[0]);
}}
""", embed_files.keys(), range(len(embed_files))))}
    return nullptr;
}}
""")
    
    if isinstance(info, grain.package.ApplicationInfo):
        final_code.append("""
int main(int argc, char** argv) {
    _grain_argc = argc;
    _grain_argv = argv;
    
    entrypoint();
    return 0;
}
""")
    
    final_includes = list(filter(grain.utils.has_file_in_dir, map(pathlib.Path, final_includes)))
    
    return FinalSource(
        code="\n".join(final_code),
        includes=final_includes,
        links=final_links,
        platform_links=list(reversed(platform_links)),
        is_app=isinstance(info, grain.package.ApplicationInfo)
    )

def generate_build_command(config: grain.config.Config, final_source: FinalSource, build_config: BuildConfig):
    if not final_source.is_app:
        raise Exception("Cannot build a library as an executable")
    
    source_path = config.ensure_default_build_path() / "source.cpp"
    source_path.write_text(final_source.code, encoding="utf-8")
    
    result = [
        config.compiler_gpp,
        "-std=c++20", "-static",
        "-O3" if build_config.is_release else "-O0",
        "" if build_config.is_release else "-ggdb",
        "-ffunction-sections" if build_config.is_release else "",
        "-fdata-sections" if build_config.is_release else "",
        "-Wsign-compare",
        "-Wa,-mbig-obj",
        *map(lambda x: f"-I{x}", final_source.includes),
        str(source_path),
        *final_source.links,
        *map(lambda x: f"-l{x}", final_source.platform_links),
        "-Wl,--gc-sections" if build_config.is_release else "",
        "-s" if build_config.is_release else "",
        "-o", build_config.output,
    ]
    
    return list(filter(bool, result))

def build(config: grain.config.Config, app_dir: pathlib.Path, build_config: BuildConfig):
    final_source = generate_final_source(config.get_storage(), config.data_dir_as_path(), app_dir, build_config)
    command = generate_build_command(config, final_source, build_config)
    Logger.info("Compiling application:", command)
    
    pro = subprocess.run(command)
    pro.check_returncode()
    
    if build_config.run_immediately:
        subprocess.run([build_config.output])

def pack(config: grain.config.Config, app_dir: pathlib.Path, build_config: BuildConfig):
    final_source = generate_final_source(config.get_storage(), config.data_dir_as_path(), app_dir, build_config)
    zippath = pathlib.Path(build_config.output).with_suffix(".zip")
    Logger.info("Packing library to", zippath)
    
    zip = zipfile.ZipFile(zippath, "w", zipfile.ZIP_STORED)
    zip.writestr("lib.hpp", final_source.code)
    
    for dir in final_source.includes:
        grain.utils.walk_dir(dir, lambda p: zip.write(p, f"includes/{p.relative_to(dir)}"))
    
    link_catalog = {}
    
    for link in final_source.links:
        name = f"{uuid.uuid4().hex}.a"
        zip.write(link, f"libs/{name}")
        link_catalog[link] = name
    
    zip.writestr("hint.json", json.dumps({
        "platform_links": final_source.platform_links,
        "linking_order": [
            link_catalog[i]
            for i in final_source.links
        ]
    }, **grain.utils.jdump_args()))
    
