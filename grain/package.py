import pathlib
import dataclasses
import string
import json

import grain.utils

def get_package_info_path(pkg_dir: pathlib.Path):
    return pkg_dir / "info.json"

def check_package_name(name: str):
    if not (1 <= len(name.encode("utf-8")) <= 64):
        return False
    
    if any(map(lambda x: x not in string.ascii_letters + string.digits + "_", name)):
        return False
    
    if name.startswith("_") or name.endswith("_") or name.startswith(tuple(string.digits)):
        return False

    return True

@dataclasses.dataclass
class PackageBaseInfo:
    requirements: grain.utils.Requirements = dataclasses.field(default_factory=grain.utils.Requirements)
    
    @staticmethod
    def load(data: dict):
        return PackageBaseInfo(
            requirements=grain.utils.Requirements.load(data["requirements"])
        )
    
    def dump(self):
        return {
            "requirements": self.requirements.dump()
        }

@dataclasses.dataclass
class LibraryExports:
    includes: grain.utils.PlatformBasedData[list[str]] = dataclasses.field(default_factory=lambda: grain.utils.PlatformBasedData([]))
    libs: grain.utils.PlatformBasedData[list[str]] = dataclasses.field(default_factory=lambda: grain.utils.PlatformBasedData([]))
    
    @staticmethod
    def load(data: dict):
        return LibraryExports(
            includes=grain.utils.PlatformBasedData(data["includes"]),
            libs=grain.utils.PlatformBasedData(data["libs"])
        )
    
    def dump(self):
        return {
            "includes": self.includes.data,
            "libs": self.libs.data
        }

@dataclasses.dataclass
class LibraryInfo(PackageBaseInfo):
    namespace: str = ""
    exports: LibraryExports = dataclasses.field(default_factory=LibraryExports)
    
    @staticmethod
    def load(data: dict):
        return LibraryInfo(
            namespace=data["namespace"],
            exports=LibraryExports.load(data["exports"]),
            **PackageBaseInfo.load(data).__dict__
        )
    
    def dump(self):
        return {
            **super().dump(),
            "type": "library",
            "namespace": self.namespace,
            "exports": self.exports.dump()
        }

@dataclasses.dataclass
class ApplicationInfo(PackageBaseInfo):
    name: str = ""
    
    @staticmethod
    def load(data: dict):
        return ApplicationInfo(
            name=data["name"],
            **PackageBaseInfo.load(data).__dict__
        )
    
    def dump(self):
        return {
            **super().dump(),
            "type": "application",
            "name": self.name
        }

def load_package_info_from_dict(data: dict):
    typ = data["type"]
    if typ == "library": return LibraryInfo.load(data)
    elif typ == "application": return ApplicationInfo.load(data)
    else: raise ValueError(f"Unknown package type: {typ}")

def load_package_info(pkg_dir: pathlib.Path):
    with open(get_package_info_path(pkg_dir), "r") as f:
        data = json.load(f)
    return load_package_info_from_dict(data)

type UnionPackageInfo = LibraryInfo | ApplicationInfo

def get_name_from_info(info: UnionPackageInfo):
    return info.name if isinstance(info, ApplicationInfo) else info.namespace

def get_name_from_package(pkg_dir: pathlib.Path):
    return get_name_from_info(load_package_info(pkg_dir))

def get_source_filename(info: UnionPackageInfo):
    return "lib.hpp" if isinstance(info, LibraryInfo) else "main.cpp"

def get_default_source(info: UnionPackageInfo):
    if isinstance(info, LibraryInfo):
        return f"""\
namespace {info.namespace} {{
    // code goes here
}}
"""
    else:
        return f"""\
void entrypoint() {{
    // code goes here
}}
"""

def get_path_relative_to_package(pkg_dir: pathlib.Path, path: pathlib.Path):
    return pathlib.Path(f"{pkg_dir}/files/{path}")
