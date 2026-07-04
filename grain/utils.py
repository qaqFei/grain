import typing
import dataclasses
import pathlib
import platform

def get_current_platform():
    """
    Returns <name>::<arch> string for the current platform
    
    <name> is one of "windows", "linux", "macos"
    <arch> is one of "x86_64", "i386", "arm64"
    """
    
    system = platform.system().lower()
    if system == "windows": os_name = "windows"
    elif system == "darwin": os_name = "macos"
    elif system == "linux": os_name = "linux"
    else: raise ValueError(f"Unsupported operating system: {system}")
    
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64", "x64"): arch = "x86_64"
    elif machine in ("i386", "i686", "x86"): arch = "i386"
    elif machine in ("arm64", "aarch64"): arch = "arm64"
    else: raise ValueError(f"Unsupported architecture: {machine}")
    
    return f"{os_name}::{arch}"
    
PlatformBasedListT = typing.TypeVar("PlatformBasedListT")
class PlatformBasedList(typing.Generic[PlatformBasedListT]):
    data: list[PlatformBasedListT]|dict[str, list[PlatformBasedListT]]
    
    def __init__(self, data: list[PlatformBasedListT]|dict[str, list[PlatformBasedListT]]):
        self.data = data
        
    def get(self, platform: typing.Optional[str] = None) -> list[PlatformBasedListT]:
        if not isinstance(self.data, dict): return self.data
        
        if platform is None:
            platform = get_current_platform()
        
        sys, _ = platform.split("::")
        result = []
        
        for key, value in self.data.items():
            if key == platform or key == sys or key == "default":
                result.extend(value)
        
        return result
    
    def get_all(self) -> typing.Iterable[PlatformBasedListT]:
        if isinstance(self.data, dict): yield from self.data.values()
        else: yield self.data

@dataclasses.dataclass
class Requirements:
    externals: PlatformBasedList[str] = dataclasses.field(default_factory=lambda: PlatformBasedList([]))
    standards: PlatformBasedList[str] = dataclasses.field(default_factory=lambda: PlatformBasedList([]))
    platform_links: PlatformBasedList[str] = dataclasses.field(default_factory=lambda: PlatformBasedList([]))
    
    @staticmethod
    def load(data: dict):
        return Requirements(
            externals=PlatformBasedList(data.get("externals", [])),
            standards=PlatformBasedList(data.get("standards", [])),
            platform_links=PlatformBasedList(data.get("platform_links", []))
        )
    
    def dump(self):
        return {
            "externals": self.externals.data,
            "standards": self.standards.data,
            "platform_links": self.platform_links.data
        }
        
def walk_dir(path: pathlib.Path, callback: typing.Callable[[pathlib.Path], typing.Any]):
    for p in path.rglob('*'):
        if p.is_file() and not p.is_symlink():
            callback(p)

def jdump_args():
    return {
        "indent": 4,
        "ensure_ascii": False
    }

def parse_package_name(name: str):
    name, version = name.split("==")
    return name, int(version)
