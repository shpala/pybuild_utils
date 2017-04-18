#!/usr/bin/env python

import os
import re
import subprocess
import tarfile
from urllib.request import urlopen


class BuildError(Exception):
    def __init__(self, value):
        self.value_ = value

    def __str__(self):
        return self.value_


class CompileInfo(object):
    def __init__(self, patches: list, flags: list):
        self.patches_ = patches
        self.flags_ = flags

    def patches(self):
        return self.patches_

    def flags(self):
        return self.flags_

    def extend_flags(self, other_args):
        self.flags_.extend(other_args)


def read_file_line_by_line(file) -> list:
    if not os.path.exists(file):
        raise BuildError('file path: %s not exists' % file)

    file_array = []
    with open(file, "r") as ins:
        for line in ins:
            file_array.append(line.strip())

    return file_array


def download_file(url, current_dir):
    file_name = url.split('/')[-1]
    responce = urlopen(url)
    if responce.status != 200:
        raise BuildError(
            "Can't fetch url: %s, status: %s, responce: %s" % (url, responce.status, responce.reason))

    f = open(file_name, 'wb')
    file_size = 0
    header = responce.getheader("Content-Length")
    if header:
        file_size = int(header)

    print("Downloading: %s Bytes: %s" % (file_name, file_size))

    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = responce.read(block_sz)
        if not buffer:
            break

        file_size_dl += len(buffer)
        f.write(buffer)
        percent = 0 if not file_size else file_size_dl * 100. / file_size
        status = r"%10d  [%3.2f%%]" % (file_size_dl, percent)
        status += chr(8) * (len(status) + 1)
        print(status, end='\r')

    f.close()
    return os.path.join(current_dir, file_name)


def extract_file(path, current_dir):
    print("Extracting: {0}".format(path))
    try:
        tar_file = tarfile.open(path)
    except Exception as ex:
        raise ex

    target_path = os.path.commonprefix(tar_file.getnames())
    try:
        tar_file.extractall()
    except Exception as ex:
        raise ex
    finally:
        tar_file.close()

    return os.path.join(current_dir, target_path)


def build_command_configure(compiler_flags: CompileInfo, prefix_path):
    # patches
    script_dir = os.path.dirname(g_script_path)

    for dir in compiler_flags.patches():
        scan_dir = os.path.join(script_dir, dir)
        if os.path.exists(scan_dir):
            for diff in os.listdir(scan_dir):
                if re.match(r'.+\.patch', diff):
                    patch_file = os.path.join(scan_dir, diff)
                    line = 'patch -p0 < {0}'.format(patch_file)
                    subprocess.call(['bash', '-c', line])

    compile_cmd = ['./configure', '--prefix={0}'.format(prefix_path)]
    compile_cmd.extend(compiler_flags.flags())
    subprocess.call(compile_cmd)
    subprocess.call(['make', '-j2'])
    subprocess.call(['make', 'install'])


def build_from_sources(url, compiler_flags: CompileInfo, prefix_path):
    pwd = os.getcwd()
    file_path = download_file(url, pwd)
    extracted_folder = extract_file(file_path, pwd)
    os.chdir(extracted_folder)
    build_command_configure(compiler_flags, prefix_path)
    os.chdir(pwd)
    shutil.rmtree(extracted_folder)


def git_clone(url, current_dir):
    common_git_clone_line = ['git', 'clone', url]
    cloned_dir = os.path.splitext(url.rsplit('/', 1)[-1])[0]
    common_git_clone_line.append(cloned_dir)
    subprocess.call(common_git_clone_line)
    os.chdir(cloned_dir)

    common_git_clone_init_line = ['git', 'submodule', 'update', '--init', '--recursive']
    subprocess.call(common_git_clone_init_line)
    return os.path.join(current_dir, cloned_dir)
