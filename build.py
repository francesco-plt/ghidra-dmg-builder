#!/usr/bin/env python3

from colored_traceback import add_hook as colored_traceback_add_hook
from IPython import embed

from argparse import ArgumentParser
from os import chdir, environ, path, symlink
from pathlib import Path
from plistlib import dump, loads
from requests import get
from shutil import copytree, copy, rmtree
from subprocess import CalledProcessError, run
from tempfile import gettempdir, TemporaryDirectory

GHIDRA_RELEASE_API_URL = (
    "https://api.github.com/repos/NationalSecurityAgency/ghidra/releases/latest"
)
GRAALVM_RELEASE_API_URL = (
    "https://api.github.com/repos/graalvm/graalvm-ce-builds/releases/latest"
)
DL_CHUNK_SIZE = 1024

SCRIPT_PATH = Path(__file__).parent
INFO_PLIST_PATH = SCRIPT_PATH / "assets" / "Info.plist"
ICON_PATH = SCRIPT_PATH / "assets" / "GhidraIcon.png"
LAUNCHER_PATH = SCRIPT_PATH / "assets" / "ghidra"

# only works with github api link to latest release of some repo
def release_dl_link(api_url, asset_name_filters=None):

    r = get(api_url)
    if r.status_code != 200:
        raise Exception(
            f"[+] Request to {api_url} failed with status code {r.status_code}"
        )

    if asset_name_filters is not None:
        for asset in r.json()["assets"]:
            if all([filter in asset["name"] for filter in asset_name_filters]):
                return asset["name"], asset["browser_download_url"]
    else:
        return (
            r.json()["assets"][0]["name"],
            r.json()["assets"][0]["browser_download_url"],
        )


def download_file(url, dl_path: Path):

    if not dl_path.exists():
        with open(dl_path, "wb") as f:
            with get(url, stream=True) as r:
                for chunk in r.iter_content(chunk_size=DL_CHUNK_SIZE):
                    f.write(chunk)


def clone_repository(git_url, destination: Path):
    if not destination.exists():
        run(f"git clone %s %s" % (git_url, destination), shell=True)
        print(f"[+] Cloned repository {git_url} to {destination}")
        # returning a path of the type download-folder-name/repository-folder-name
        return destination / git_url.split("/")[-1][:-4]


def build_ghidra_extension(ghidra_home: Path, extension_path: Path, java_home=None):
    build_command = ["gradle"]
    build_environment = {"GHIDRA_INSTALL_DIR": str(ghidra_home)}
    if java_home:
        build_environment["PATH"] = f"{java_home / 'bin'}:{environ['PATH']}"
        build_environment["JAVA_HOME"] = str(java_home)
    run(build_command, env=build_environment, cwd=extension_path, shell=True)
    distribution_zip = next((extension_path / "dist").glob("*.zip"))
    return distribution_zip


def build_image(in_path: Path, out_path: Path):

    name = "Ghidra"
    dst = Path(f"{name}.dmg")

    if dst.exists():
        dst.unlink()

    try:
        run(
            f"hdiutil create -volname %s -fs HFS+ -srcfolder %s %s.dmg"
            % (name, in_path, out_path / name),
            shell=True,
            check=True,
        )
    except CalledProcessError:
        # we need to delete the dmg if it already exists
        if (out_path / dst).exists():
            (out_path / dst).unlink()
        run(
            f"hdiutil create -volname %s -fs HFS+ -srcfolder %s %s.dmg"
            % (name, in_path, out_path / name),
            shell=True,
            check=True,
        )


def argparse_setup():
    parser = ArgumentParser()
    parser.add_argument(
        "-o",
        "--out",
        "--output-path",
        help="Path in which you want the generated .dmg to be stored",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "-e",
        "--extension",
        type=Path,
        default=[],
        nargs="*",
        help="Repository HTTPS clone URL to a Ghidra extension",
    )
    parser.add_argument(
        "-d",
        "--dark-mode",
        action="store_true",
        help="Enable GUI dark mode",
    )
    parser.add_argument("-p", "--path", help="Path to Ghidra zip or install", type=Path)

    # adding the option to choose an sdk compatible with a bunch of interpreted languages
    jdk_group = parser.add_mutually_exclusive_group()
    jdk_group.add_argument(
        "-j", "--jdk", help="Path to a JDK directory to bundle", type=Path
    )
    jdk_group.add_argument(
        "-g",
        "--graal",
        action="store_true",
        help="Bundle the Graal VM and Ghidraal for Python3 support",
    )
    return parser.parse_args()


def main():

    colored_traceback_add_hook()
    args = argparse_setup()

    dl_dir = Path("/tmp", "ghidra_dmg_builder_downloads")
    # script parent folder + assets/icon.icns

    print(f"[+] Downloads will be cached to {dl_dir}")

    # either an existing zip file path is provided, or we download the latest zipped version from github
    if args.path:
        ghidra_zip_fname = args.path.name
        ghidra_version = ghidra_zip_fname.split("ghidra_")[1].split("_")[0]
    else:
        print("[!] No path provided, checking if cached version exists...")
        dl_dir.mkdir(exist_ok=True)
        ghidra_zip_fname, ghidra_url = release_dl_link(GHIDRA_RELEASE_API_URL)

        ghidra_version = ghidra_zip_fname.split("ghidra_")[1].split("_")[0]

        if not path.exists(dl_dir / ghidra_zip_fname):
            print(f"[+] Downloading {ghidra_zip_fname} from {ghidra_url}...")
            download_file(ghidra_url, dl_dir / ghidra_zip_fname)

    print(f"[-] Will use Ghidra {ghidra_version} from {ghidra_zip_fname}, ")

    """
    Exepcted output:
        Ghidra.dmg/Ghidra.app/
        └── Contents
            ├── Info.plist
            ├── MacOS
            │   └── ghidra
            └── Resources
                ├── Ghidra.icns
                └── ghidra_x.x.x_PUBLIC
                └── [ Extensions ]
    """

    in_path = Path("/tmp", "ghidra_dmg_builder_cache")
    in_path.mkdir(exist_ok=True)
    release_path = None
    contents_path = None
    resources_path = None
    release_path = None

    (in_path / "Ghidra.app").mkdir(exist_ok=True)  # Ghidra.dmg/Ghidra.app

    if not (in_path / "Applications").exists():
        symlink("/Applications", in_path / "Applications")  # Ghidra.dmg/Applications

    contents_path = in_path / "Ghidra.app" / "Contents"
    resources_path = contents_path / "Resources"
    release_path = resources_path / f"ghidra_{ghidra_version}_PUBLIC"

    contents_path.mkdir(parents=True, exist_ok=True)  # Ghidra.dmg/Ghidra.app/Contents

    resources_path.mkdir(
        parents=True, exist_ok=True
    )  # Ghidra.dmg/Ghidra.app/Contents/Resources

    (contents_path / "MacOS").mkdir(
        parents=True, exist_ok=True
    )  # Ghidra.dmg/Ghidra.app/Contents/MacOS

    # Ghidra.dmg/Ghidra.app/Contents/Info.plist
    print(f"[+] Setting bundle version to {ghidra_version}...")
    with open(INFO_PLIST_PATH, "rb") as plist_file:
        info = loads(plist_file.read())
    info["CFBundleVersion"] = ghidra_version
    with open(contents_path / "Info.plist", "wb") as plist_file:
        dump(info, plist_file)  # Ghidra.dmg/Ghidra.app/Contents/Info.plist

    # Ghidra.dmg/Ghidra.app/Contents/Resources/Ghidra.icns
    print("[+] Setting app icon...")
    copy(SCRIPT_PATH / "assets" / "Ghidra.icns", resources_path)

    # Ghidra.dmg/Ghidra.app/Contents/MacOS/ghidra
    print("[+] Copying launcher script...")
    copy(LAUNCHER_PATH, contents_path / "MacOS" / "ghidra")
    run(f"chmod +x %s" % (contents_path / "MacOS" / "ghidra"), shell=True)

    # Ghidra.dmg/Ghidra.app/Contents/MacOS/ghidra_X.X_PUBLIC
    # Either we use the provided path (both zipped and extracted are ok),
    # or we either extract the zip file or just copy the cached unzipped
    # folder to destination
    if args.path:
        if args.path.is_dir():
            copytree(args.path, release_path)
        else:
            run(
                f"unzip -f %s -d %s" % (args.path, release_path.parent),
                shell=True,
            )
    elif not release_path.exists():
        if not (dl_dir / f"ghidra_{ghidra_version}_PUBLIC").exists():
            run(
                f"unzip -n %s -d %s" % (dl_dir / ghidra_zip_fname, dl_dir),
                shell=True,
            )
        copytree(dl_dir / f"ghidra_{ghidra_version}_PUBLIC", release_path)

    # Ghidra.dmg/Ghidra.app/Contents/Resources/ghidra_10.X.X_PUBLIC/Ghidra/Framework/Generic/lib/Generic.jar
    # Patching Generic.jar to show the same icon on the dock
    print("[+] Patching Generic.jar to show the same icon on the dock...")

    """
    ok this is a bit of a hack, but it works
    basically the 'jar' cli tool has some problem working with
    absolute paths, so we need to chdir to the release_path, copy
    there the icon, patch the jar and finally chdir back to the script path
    """

    images_path = release_path / "images"
    images_path.mkdir(exist_ok=True)

    chdir(release_path)
    for res in [16, 32, 40, 48, 64, 128, 256]:
        run(
            "convert %s -resize %sx%s %s/GhidraIcon%s.png"
            % (ICON_PATH, res, res, images_path, res),
            shell=True,
        )
        run(
            f"jar -u -f Ghidra/Framework/Generic/lib/Generic.jar images/GhidraIcon{res}.png",
            shell=True,
        )
    chdir(SCRIPT_PATH)

    print("[+] Patching launch.properties to enable menu bar settings...")
    with open(release_path / "support" / "launch.properties", "r") as launch_properties:
        launch_properties_data = launch_properties.read()

    # Replace the target string
    launch_properties_data = launch_properties_data.replace(
        "useScreenMenuBar=false", "useScreenMenuBar=true"
    )

    with open(release_path / "support" / "launch.properties", "w") as launch_properties:
        launch_properties.write(launch_properties_data)

    # setting dark mode
    if args.dark_mode:
        print("[+] Setting dark mode...")
        darkmode_repo_path = dl_dir / "dark-mode"
        clone_repository(
            "https://github.com/zackelia/ghidra-dark.git", darkmode_repo_path
        )
        run(
            f"python3 %s --path %s" % (darkmode_repo_path / "install.py", release_path),
            shell=True,
        )

    # embedding the JDK if requested
    if args.jdk:
        jdk_path = resources_path / "jdk"

        if args.jdk.is_file():
            print("[+] Extracting...")
            run(f"unzip -d %s %s" % (jdk_path, args.jdk), shell=True)
            print("[+] JDK Extracted to {}".format(jdk_path))
        if args.jdk.is_dir():
            print("[+] Copying...")
            copytree(args.jdk, jdk_path)
            print("[+] JDK Copied to {}".format(jdk_path))

    # embedding the Graal VM if requested
    if args.graal:

        # grabbing the Graal VM from Github
        graalvm_zip, graalvm_url = release_dl_link(
            GRAALVM_RELEASE_API_URL, ["tar.gz", "graalvm-ce-java11", "darwin"]
        )
        download_file(graalvm_url, dl_dir / graalvm_zip)
        graal_dirname = (
            dl_dir / graalvm_zip.replace("darwin-amd64-", "").split(".tar.gz")[0]
        )
        # extracting the VM
        run(
            f"tar -C %s -xvf %s" % (dl_dir / graal_dirname, dl_dir / graalvm_zip),
            shell=True,
            check=True,
        )
        # and installing it
        print("[+] Installing graal VM components")
        run(
            f"%s/Contents/Home/bin/gu install llvm-toolchain native-image nodejs python ruby R wasm"
            % (dl_dir / graal_dirname),
            shell=True,
        )

        # Now that we've primed our cached version of graal with the various language components
        # we can install it into our Ghidra bundle

        # We must not already have a JDK path, if we do we'll end up with a 'Home' directory
        # inside the JDK path, which will break the launcher script.
        print("[+] Copying Graal to Ghidra bundle")
        graal_dest_path = resources_path / "graal"
        graal_dest_path.mkdir()
        # Now copy the primed cache into our bundle. Note the archive parameter, we need to preserve
        # symlinks or graal will get sad
        run(
            f"rsync --archive --recursive %s %s" % (graal_dirname, graal_dest_path),
            shell=True,
        )
        graal_home = next(graal_dest_path.glob("*")) / "Contents" / "Home"
        # The path looks like
        # graalvm-ce-java11-21.3.0/Contents/Home/...
        jdk_path.symlink_to(graal_home.relative_to(resources_path))
        # Now we'll check that our copied graal works for good measure
        run(f"%s/bin/gu list" % (graal_home), shell=True)

        # Now we have Graal installed, lets ensure we get the Ghidraal extension
        print("[+] Building Ghidraal extension")
        ghidraal_repo_path = dl_dir / "ghidraal"
        clone_repository("https://github.com/jpleasu/ghidraal.git", ghidraal_repo_path)
        # Ghidraal seems to have a broken gradle.build file, so we'll patch it
        (ghidraal_repo_path / "build.gradle").unlink()
        copy(
            args.out.parent / "Resources" / "build.gradle",
            ghidraal_repo_path / "build.gradle",
        )
        ghidraal_extension = build_ghidra_extension(
            release_path, ghidraal_repo_path, java_home=jdk_path
        )
        # Pretend the user specified this on the command line
        print("[+] Adding Ghidraal to the selected extensions for installation")
        args.extension.append(ghidraal_extension)

    if args.extension:
        print("[+] extension flag detected. Installing extensions...")
        extensions_path = release_path / "Ghidra" / "Extensions"
        for ext_path in args.extension:

            # first we want to check if 'ext_path' is an url or a filesystem path
            if ext_path.startswith("http"):
                # if the user specified an url to the github repository of an extension,
                # we'll first obtain the name of the extension from the url
                ext_name = ext_path.split("/")[-1][:-4]
            else:
                # if the user specified a path to the extension, we'll extract the name from the path
                ext_name = ext_path.split("/")[-1]

            print(f"[+] Installing extension from {ext_path}...")
            # handling the url case
            if ext_path.startswith("http"):
                clone_repository(ext_path, dl_dir / ext_name)
                ext_source_path = dl_dir / ext_name
            else:
                # if it's a zip we extract it and set the extension path
                # as the name of the extracted folder
                if ext_path.endswith(".zip"):
                    run(f"unzip -d %s %s" % (extensions_path, ext_path), shell=True)
                    ext_path = ext_name
                # we handle implicitly the easiest case (i.e. when the argument is a path to the extension)
                ext_source_path = Path(ext_path)

            outpath = build_ghidra_extension(release_path, ext_source_path)
            copy(outpath, extensions_path)
            print(f"[+] Extension {ext_name} installed")

    # now we just need to build the image
    print("[+] Building dmg...")
    build_image(in_path, args.out)
    rmtree(in_path)


if __name__ == "__main__":
    main()
