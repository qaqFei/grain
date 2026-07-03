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
    
PlatformBasedDataT = typing.TypeVar("PlatformBasedDataT")
class PlatformBasedData(typing.Generic[PlatformBasedDataT]):
    data: PlatformBasedDataT|dict[str, PlatformBasedDataT]
    
    def __init__(self, data: PlatformBasedDataT|dict[str, PlatformBasedDataT]):
        self.data = data
        
    def get(self, platform: typing.Optional[str] = None) -> PlatformBasedDataT:
        if platform is None:
            platform = get_current_platform()
        
        if isinstance(self.data, dict):
            return self.data.get(platform)
        else:
            return self.data
    
    def get_all(self) -> typing.Iterable[PlatformBasedDataT]:
        if isinstance(self.data, dict): yield from self.data.values()
        else: yield self.data

@dataclasses.dataclass
class Requirements:
    externals: PlatformBasedData[list[str]] = dataclasses.field(default_factory=lambda: PlatformBasedData([]))
    standards: PlatformBasedData[list[str]] = dataclasses.field(default_factory=lambda: PlatformBasedData([]))
    
    @staticmethod
    def load(data: dict):
        return Requirements(
            externals=PlatformBasedData(data["externals"]),
            standards=PlatformBasedData(data["standards"])
        )
    
    def dump(self):
        return {
            "externals": self.externals.data,
            "standards": self.standards.data
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
