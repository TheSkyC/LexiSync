# Copyright (c) 2025, TheSkyC
# SPDX-License-Identifier: Apache-2.0

import os
import sys
import subprocess
import argparse
import shutil

APP_NAME = "overwatch_localizer"

LOCALE_DIR = "locales"

SOURCE_DIRS = ['.', 'components', 'dialogs', 'services', 'utils']
# Support Language
LANGUAGES = ['en_US', 'zh_CN']

# POT 文件元数据
POT_HEADER = {
    'Project-Id-Version': 'Overwatch Localizer 1.0.3',
    'Report-Msgid-Bugs-To': 'your-email@example.com',
    'POT-Creation-Date': '',  # 会自动生成
    'PO-Revision-Date': 'YEAR-MO-DA HO:MI+ZONE',
    'Last-Translator': 'FULL NAME <EMAIL@ADDRESS>',
    'Language-Team': 'LANGUAGE <LL@li.org>',
    'MIME-Version': '1.0',
    'Content-Type': 'text/plain; charset=UTF-8',
    'Content-Transfer-Encoding': '8bit',
}
# --- 结束配置 ---

POT_FILE = os.path.join(LOCALE_DIR, f'{APP_NAME}.pot')


def find_gettext_tool(tool_name):
    """在系统 PATH 和 Python Scripts 目录中查找 gettext 工具"""
    if shutil.which(tool_name):
        return tool_name

    # 尝试在 Python 的 Scripts 目录中查找
    python_executable = sys.executable
    python_dir = os.path.dirname(python_executable)

    # Windows 上的 Scripts 目录
    scripts_path = os.path.join(python_dir, 'Scripts', f'{tool_name}.exe')
    if os.path.exists(scripts_path):
        return scripts_path

    # Linux/macOS 上的 bin 目录
    bin_path = os.path.join(python_dir, 'bin', tool_name)
    if os.path.exists(bin_path):
        return bin_path

    return None


def find_pygettext():
    """查找 pygettext.py 脚本"""
    python_executable = sys.executable
    python_dir = os.path.dirname(python_executable)

    # 标准库中的位置
    pygettext_path = os.path.join(python_dir, 'Tools', 'i18n', 'pygettext.py')
    if os.path.exists(pygettext_path):
        return [python_executable, pygettext_path]

    # 有时它可能在 Scripts 目录
    scripts_path = os.path.join(python_dir, 'Scripts', 'pygettext.py')
    if os.path.exists(scripts_path):
        return [python_executable, scripts_path]

    # 如果都找不到，尝试直接运行命令
    if shutil.which('pygettext.py'):
        return ['pygettext.py']
    if shutil.which('pygettext'):
        return ['pygettext']

    return None


def run_command(command):
    """执行一个 shell 命令并打印输出"""
    print(f"Executing: {' '.join(command)}")
    try:
        # 使用 utf-8 编码以支持非 ASCII 字符
        result = subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print(f"\n[ERROR] Command '{command[0]}' not found.")
        print("Please ensure that gettext tools are installed and accessible in your system's PATH.")
        print("On Windows, you can download them from: https://mlocati.github.io/articles/gettext-iconv-windows.html")
        print("On Debian/Ubuntu: sudo apt-get install gettext")
        print("On macOS (with Homebrew): brew install gettext\n")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {' '.join(command)}")
        print(e.stdout)
        print(e.stderr)
        sys.exit(1)


def extract_strings():
    """从源文件中提取所有待翻译的字符串到 .pot 模板文件"""
    print("--- 1. Extracting strings to .pot file ---")
    if not os.path.exists(LOCALE_DIR):
        os.makedirs(LOCALE_DIR)

    source_files = []
    for src_dir in SOURCE_DIRS:
        for root, _, files in os.walk(src_dir):
            for file in files:
                if file.endswith('.py'):
                    source_files.append(os.path.join(root, file))

    pygettext_cmd = find_pygettext()
    if not pygettext_cmd:
        print("\n[ERROR] `pygettext.py` script not found.")
        print("It's usually part of the Python standard library in the 'Tools/i18n' directory.")
        print("Please ensure your Python installation is complete or install gettext tools manually.\n")
        sys.exit(1)

    command = pygettext_cmd + [
        '-d', APP_NAME,
        '-o', POT_FILE,
        f'--project={POT_HEADER["Project-Id-Version"]}',
        f'--msgid-bugs-address={POT_HEADER["Report-Msgid-Bugs-To"]}',
        '--keyword=_',  # 查找 _() 函数
    ] + source_files

    run_command(command)
    print(f"Successfully created template file: {POT_FILE}")


def update_po_files():
    """使用 .pot 文件更新或创建每个语言的 .po 文件"""
    print("\n--- 2. Updating .po files ---")

    msginit_tool = find_gettext_tool('msginit')
    msgmerge_tool = find_gettext_tool('msgmerge')

    if not msginit_tool or not msgmerge_tool:
        print("\n[ERROR] `msginit` or `msgmerge` not found. Please install gettext tools.\n")
        sys.exit(1)

    for lang in LANGUAGES:
        lang_dir = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES')
        if not os.path.exists(lang_dir):
            os.makedirs(lang_dir)

        po_file = os.path.join(lang_dir, f'{APP_NAME}.po')

        if not os.path.exists(po_file):
            print(f"Creating new .po file for {lang}...")
            command = [msginit_tool, '--no-translator', '-l', lang, '-i', POT_FILE, '-o', po_file]
            run_command(command)
        else:
            print(f"Updating existing .po file for {lang}...")
            command = [msgmerge_tool, '--update', '--backup=none', po_file, POT_FILE]
            run_command(command)
    print("All .po files are up to date.")


def compile_mo_files():
    """将所有 .po 文件编译成二进制的 .mo 文件"""
    print("\n--- 3. Compiling .mo files ---")

    msgfmt_tool = find_gettext_tool('msgfmt')
    if not msgfmt_tool:
        print("\n[ERROR] `msgfmt` not found. Please install gettext tools.\n")
        sys.exit(1)

    for lang in LANGUAGES:
        po_file = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', f'{APP_NAME}.po')
        mo_file = os.path.join(LOCALE_DIR, lang, 'LC_MESSAGES', f'{APP_NAME}.mo')

        if os.path.exists(po_file):
            print(f"Compiling {po_file} to {mo_file}...")
            command = [msgfmt_tool, '-o', mo_file, po_file]
            run_command(command)
        else:
            print(f"Warning: {po_file} not found, skipping compilation for {lang}.")
    print("All .mo files compiled successfully.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Translation management script for Overwatch Localizer.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'action',
        choices=['extract', 'update', 'compile', 'all'],
        help="""Action to perform:
  extract: Scan source code and create/update the .pot template file.
  update:  Update language .po files from the .pot template.
  compile: Compile .po files into binary .mo files for the app to use.
  all:     Perform all three steps in order: extract -> update -> compile."""
    )

    args = parser.parse_args()

    if args.action == 'extract':
        extract_strings()
    elif args.action == 'update':
        update_po_files()
    elif args.action == 'compile':
        compile_mo_files()
    elif args.action == 'all':
        extract_strings()
        update_po_files()
        compile_mo_files()
        print("\n--- All translation tasks completed! ---")