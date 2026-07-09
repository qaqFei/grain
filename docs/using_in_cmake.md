# Guide to Using a Package in CMake

## 1. Pack the Package

Use the Grain CLI to pack your package:

```bash
grain package pack . --out packed.zip
```

> ⚠️ Only one Grain package can be included per program. Multiple packages cannot be linked together directly due to conflicting global symbols in each package's `lib.hpp`. To use multiple, combine them into a single package first.

This command generates a `packed.zip` archive in the current directory.

## 2. Place the Package in Your Project

You can either extract the archive directly into your project directory or store it in a location that your build system can access.

Example structure:

```bash
$ ls
CMakeLists.txt  packed.zip  src/

$ mkdir grain_packages

$ unzip ./packed.zip -d ./grain_packages/gglfw3
Archive:  ./packed.zip
 extracting: ./grain_packages/gglfw3/lib.hpp
 extracting: ./grain_packages/gglfw3/includes/gglfw3/glfw3.h
 extracting: ./grain_packages/gglfw3/includes/gglfw3/glfw3native.h
 extracting: ./grain_packages/gglfw3/libs/0fb564c9203c471db7842a42b4989a74.a
 extracting: ./grain_packages/gglfw3/hint.json

$ ls ./grain_packages/gglfw3
hint.json  includes/  lib.hpp  libs/
```

## 3. Configure CMake to Use the Package

Add the following settings to your CMakeLists.txt.

### Include directories

```cmake
# Add the root grain packages directory
target_include_directories(MyApp PRIVATE ${CMAKE_SOURCE_DIR}/grain_packages)

# Add the package-specific include directory
target_include_directories(MyApp PRIVATE ${CMAKE_SOURCE_DIR}/grain_packages/gglfw3/includes)
```

### Link Libraries

Check the `hint.json` file to determine the linking order and platform-specific dependencies:

```bash
$ cat ./grain_packages/gglfw3/hint.json
{
    "platform_links": [
        "opengl32",
        "gdi32"
    ],
    "linking_order": [
        "0fb564c9203c471db7842a42b4989a74.a"
    ]
}
```

In your CMake configuration, link the static library **first**, followed by any platform-specific libraries in the order specified:

```cmake
target_link_libraries(MyApp PRIVATE
    ${CMAKE_SOURCE_DIR}/grain_packages/glfw3/libs/0fb564c9203c471db7842a42b4989a74.a
    opengl32
    gdi32
)
```

> ⚠️ The linking order must match the sequence given in hint.json to avoid unresolved symbol errors.

## 4. Use the Package in Your Code

Example usage:

```cpp
#include <gglfw3/lib.hpp>

using namespace gglfw3;

int main() {
    auto win = Window::Make();
    win->setSizeOfMonitor(0.6);
    win->create();

    while (!win->shouldClose()) {
        pollEvents();
        win->swapBuffers();
    }
}
```

## 5. Build the Example Project (MinGW)

```bash
$ rm -r build|| cmake -B build -G "MinGW Makefiles"&& cmake --build build
-- The C compiler identification is GNU 15.2.0
-- The CXX compiler identification is GNU 15.2.0
-- Detecting C compiler ABI info
-- Detecting C compiler ABI info - done
-- Check for working C compiler: D:/mingw64/bin/cc.exe - skipped
-- Detecting C compile features
-- Detecting C compile features - done
-- Detecting CXX compiler ABI info
-- Detecting CXX compiler ABI info - done
-- Check for working CXX compiler: D:/mingw64/bin/c++.exe - skipped
-- Detecting CXX compile features
-- Detecting CXX compile features - done
-- Configuring done (1.0s)
-- Generating done (0.0s)
-- Build files have been written to: C:/Users/QAQ/Desktop/example/build
[ 50%] Building CXX object CMakeFiles/MyApp.dir/src/main.cpp.obj
[100%] Linking CXX executable MyApp.exe
[100%] Built target MyApp

$ ./build/MyApp.exe # A window should appear
```
