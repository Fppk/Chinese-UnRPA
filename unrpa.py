
"""
unrpa is a tool to extract files from Ren'Py archives (.rpa).

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
"""
unrpa是从Ren'Py文件（.rpa）中提取文件的工具。

此程序是免费软件：您可以重新分发和/或修改
根据由
自由软件基金会许可证的第3版，或者
（由您选择）任何更高版本。

这个程序的发布是希望它能有用，
但没有任何保证；甚至没有
适销性为特定目的的适销性或适合性。见
GNU通用公共许可证了解更多详细信息。

你应该收到GNU通用公共许可证的副本
和这个程序。如果没有，请参见<http://www.gnu.org/licenses/>。
"""

"""
The program was modified and translated by Fppk on April 18, 2020.
We are respectful of the original author.
If you have any copyright/copyleft issues, please contact 1679126936 directly in QQ
"""
"""
此程序已被Fppk于2020年4月18日汉化并修改
我们十分尊重原作者的劳动成果和版权
如果您有版权问题，请在QQ1679126936联系我
"""

import os
import argparse
import sys
import pickle
import zlib
import traceback


class Version:
    def __init__(self, name):
        self.name = name

    def find_offset_and_key(self, file):
        raise NotImplementedError()

    def detect(self, extension, first_line):
        raise NotImplementedError()

    def __str__(self):
        return self.name


class RPA1(Version):
    def __init__(self):
        super().__init__("RPA-1.0")

    def detect(self, extension, first_line):
        return extension == ".rpi"

    def find_offset_and_key(self, file):
        return 0, None


class HeaderBasedVersion(Version):
    def __init__(self, name, header):
        super().__init__(name)
        self.header = header

    def find_offset_and_key(self, file):
        raise NotImplementedError()

    def detect(self, extension, first_line):
        return first_line.startswith(self.header)


class RPA2(HeaderBasedVersion):
    def __init__(self):
        super().__init__("RPA-2.0", b"RPA-2.0")

    def find_offset_and_key(self, file):
        offset = int(file.readline()[8:], 16)
        return offset, None


class RPA3(HeaderBasedVersion):
    def __init__(self):
        super().__init__("RPA-3.0", b"RPA-3.0")

    def find_offset_and_key(self, file):
        line = file.readline()
        parts = line.split()
        offset = int(parts[1], 16)
        key = int(parts[2], 16)
        return offset, key


class ALT1(HeaderBasedVersion):
    EXTRA_KEY = 0xDABE8DF0

    def __init__(self):
        super().__init__("ALT-1.0", b"ALT-1.0")

    def find_offset_and_key(self, file):
        line = file.readline()
        parts = line.split()
        key = int(parts[1], 16) ^ ALT1.EXTRA_KEY
        offset = int(parts[2], 16)
        return offset, key


class ZiX(HeaderBasedVersion):
    def __init__(self):
        super().__init__("ZiX-12B", b"ZiX-12B")

    def find_offset_and_key(self, file):
        # TODO: see https://github.com/Lattyware/unrpa/issues/15
        raise NotImplementedError()


RPA1 = RPA1()
RPA2 = RPA2()
RPA3 = RPA3()
ALT1 = ALT1()
ZiX = ZiX()
Versions = [RPA1, RPA2, RPA3, ALT1, ZiX]


class UnRPA:
    NAME = "提取工具"

    def __init__(self, filename, verbosity=1, path=None, mkdir=False, version=None, continue_on_error=False,
                 offset_and_key=None):
        self.verbose = verbosity
        if path:
            self.path = os.path.abspath(path)
        else:
            self.path = os.getcwd()
        self.mkdir = mkdir
        self.version = version
        self.archive = filename
        self.continue_on_error = continue_on_error
        self.offset_and_key = offset_and_key
        self.tty = sys.stdout.isatty()

    def log(self, verbosity, message):
        if self.tty and self.verbose > verbosity:
            print("{}: {}".format(UnRPA.NAME, message))

    def log_tty(self, message):
        if not self.tty and self.verbose > 1:
            print(message)

    def exit(self, message):
        sys.exit("{}: error: {}".format(UnRPA.NAME, message))

    def extract_files(self):
        self.log(0, "正在提取" + args.filename + "中")
        if self.mkdir:
            self.make_directory_structure(self.path)
        if not os.path.isdir(self.path):
            self.exit("path doesn't exist, if you want to create it, use -m.")

        index = self.get_index()
        total_files = len(index)
        for file_number, (path, data) in enumerate(index.items()):
            try:
                self.make_directory_structure(os.path.join(self.path, os.path.split(path)[0]))
                raw_file = self.extract_file(path, data, file_number, total_files)
                with open(os.path.join(self.path, path), "wb") as f:
                    f.write(raw_file)
            except BaseException as e:
                if self.continue_on_error:
                    traceback.print_exc()
                    self.log(0,
                             "提取错误（见上文），但是由于使用了--continue on error参数，所以我们将继续运行。")
                else:
                    raise Exception("试图提取文件时出错。有关详细信息，请参见嵌套异常。"
                                    "如果您希望尝试从存档中提取尽可能多的内容，请使用--continue on error参数。") from e

    def list_files(self):
        self.log(1, "列出文件: ")
        paths = self.get_index().keys()
        for path in sorted(paths):
            print(path)

    def extract_file(self, name, data, file_number, total_files):
        self.log(1, "[{:04.2%}] {:>3}".format(file_number / float(total_files), name))
        self.log_tty(name)
        offset, dlen, start = data[0]
        with open(self.archive, "rb") as f:
            f.seek(offset)
            raw_file = start + f.read(dlen - len(start))
        return raw_file

    def make_directory_structure(self, name):
        self.log(2, "正在创建目录结构: {}".format(name))
        if not os.path.exists(name):
            os.makedirs(name)

    def get_index(self):
        if not self.version:
            self.version = self.detect_version()

        if self.version == ZiX and (not self.offset_and_key):
            self.exit("此文件使用ZiX-12B格式，这种格式是不标准的，目前unrpa尚未支持。"
                      "有关更多详细信息，请参见https://github.com/Lattyware/unrpa/issues/15")
        elif not self.version:
            self.exit("此文件没有我们能识别的头部。"
                      "如果您知道文件的版本，可以尝试使用-f来提取它，而不使用头部。")

        with open(self.archive, "rb") as f:
            if self.offset_and_key:
                offset, key = self.offset_and_key
            else:
                offset, key = self.version.find_offset_and_key(f)
            f.seek(offset)
            index = pickle.loads(zlib.decompress(f.read()), encoding="bytes")
            if key is not None:
                index = self.deobfuscate_index(index, key)

        return {self.ensure_str_path(path).replace("/", os.sep): data for path, data in index.items()}

    def ensure_str_path(self, key):
        try:
            return key.decode("utf-8")
        except AttributeError:
            return key

    def detect_version(self):
        ext = os.path.splitext(self.archive)[1].lower()
        with open(self.archive, "rb") as f:
            line = f.readline()
            for version in Versions:
                if version.detect(ext, line):
                    return version
        return None

    def deobfuscate_index(self, index, key):
        return {k: self.deobfuscate_entry(key, v) for k, v in index.items()}

    def deobfuscate_entry(self, key, entry):
        if len(entry[0]) == 2:
            entry = ((offset, dlen, b"") for offset, dlen in entry)
        return [(offset ^ key, dlen ^ key, start) for offset, dlen, start in entry]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract files from the RPA archive format.")

    parser.add_argument("-v", "--verbose", action="count", dest="verbose", default=1,
                        help="解释正在做什么[默认]。")
    parser.add_argument("-s", "--silent", action="store_const", const=0, dest="verbose",
                        help="无输出")
    parser.add_argument("-l", "--list", action="store_true", dest="list", default=False,
                        help="只列出内容而不提取。")
    parser.add_argument("-p", "--path", action="store", type=str, dest="path", default=None,
                        help="将提取到设定的路径。")
    parser.add_argument("-m", "--mkdir", action="store_true", dest="mkdir", default=False,
                        help="将在提取路径中生成不存在的目录。")
    parser.add_argument("-f", "--force", action="store", type=str, dest="version", default=None,
                        help="强制使用特定版本。可能导致提取失败。已有的版本: "
                             + ", ".join(str(version) for version in Versions))
    parser.add_argument("--continue-on-error", action="store_true", dest="continue_on_error", default=False,
                        help="出现问题时尝试继续提取。")
    parser.add_argument("-o", "--offset", action="store", type=int, dest="offset", default=None,
                        help="设置用于提取ZiX-12B文件的偏移量。")
    parser.add_argument("-k", "--key", action="store", type=int, dest="key", default=None,
                        help="设置用于解码ZiX-12B存档的键。")

    parser.add_argument("filename", metavar="FILENAME", type=str, help="the RPA file to extract.")

    args = parser.parse_args()

    provided_version = None
    if args.version:
        for version in Versions:
            if args.version.lower() == version.name.lower():
                provided_version = version
                break
        else:
            parser.error("您提供的文件版本不是我们认可的版本 - 它只能是以下的一种: " +
                         ", ".join(str(version) for version in Versions))

    provided_offset_and_key = None
    if args.key and args.offset:
        provided_offset_and_key = (args.offset, args.key)
    if bool(args.key) != bool(args.offset):
        parser.error("如果设置了键或偏移量，则必须同时设置这两个值。")

    if args.list and args.path:
        parser.error("参数-path: 仅在提取时有效。")

    if args.mkdir and not args.path:
        parser.error("参数--mkdir: 仅在--path设定时有效。")

    if not args.mkdir and args.path and not os.path.isdir(args.path):
        parser.error("没有这样的目录: '{}'. 使用--mkdir来创建它".format(args.path))

    if args.list and args.verbose == 0:
        parser.error("参数--list:不能在列出列表时禁用输出。")

    if not os.path.isfile(args.filename):
        parser.error("没有这样的文件: '{}'.".format(args.filename))

    extractor = UnRPA(args.filename, args.verbose, args.path, args.mkdir, provided_version, args.continue_on_error,
                      provided_offset_and_key)
    if args.list:
        extractor.list_files()
    else:
        extractor.extract_files()
