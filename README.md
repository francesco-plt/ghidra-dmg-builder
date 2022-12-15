# ghidra-dmg-generator

## Usage

```shell
usage: build.py [-h] -o OUT [-e [EXTENSION ...]] [-d] [-p PATH]
                [-j JDK | -g]

options:
  -h, --help            show this help message and exit
  -o OUT, --out OUT, --output-path OUT
                        Path in which you want the generated .dmg to be
                        stored
  -e [EXTENSION ...], --extension [EXTENSION ...]
                        Repository HTTPS clone URL to a Ghidra extension
  -d, --dark-mode       Enable GUI dark mode
  -p PATH, --path PATH  Path to Ghidra zip or install
  -j JDK, --jdk JDK     Path to a JDK directory to bundle
  -g, --graal           Bundle the Graal VM and Ghidraal for Python3
                        support

```
Note that `-j` and `-g` are still glitchy.

## Credits

* **Ghidra dark**: [zackelia/ghidra-dark: Dark theme installer for Ghidra (github.com)](https://github.com/zackelia/ghidra-dark)
* **Graal**: [oracle/graal: GraalVM: Run Programs Faster Anywhere (github.com)](https://github.com/oracle/graal)
* **Ghidraal**: [jpleasu/ghidraal: A Ghidra extension for scripting with GraalVM languages, including Javascript, Python3, R, and Ruby. (github.com)](https://github.com/jpleasu/ghidraal)

