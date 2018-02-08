#!/usr/bin/env python3

import errno
import os
import stat
import re
import shutil
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


def is_valid_email(email: str) -> bool:
    if not re.match('[^@]+@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$', email):
        return False

    return True


def is_role_based_email(email: str) -> bool:
    r = re.compile('([^@]+)@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$')
    match = r.match(email)
    if not match:
        return False

    start = match.group(1)
    for x in ['noreply', 'support', 'admin', 'postmaster']:
        if start == x:
            return True

    return False


def read_file_line_by_line_to_list(file) -> list:
    if not os.path.exists(file):
        raise BuildError('file path: {0} not exists'.format(file))

    file_array = []
    with open(file, "r") as ins:
        for line in ins:
            file_array.append(line.strip())

    return file_array


def read_file_line_by_line_to_set(file) -> set:
    if not os.path.exists(file):
        raise BuildError('file path: {0} not exists'.format(file))

    file_set = set()
    with open(file, "r") as ins:
        for line in ins:
            file_set.add(line.strip())

    return file_set


def download_file(url, current_dir):
    file_name = url.split('/')[-1]
    response = urlopen(url)
    if response.status != 200:
        raise BuildError(
            "Can't fetch url: {0}, status: {1}, response: {2}".format(url, response.status, response.reason))

    f = open(file_name, 'wb')
    file_size = 0
    header = response.getheader("Content-Length")
    if header:
        file_size = int(header)

    print("Downloading: {0} Bytes: {1}".format(file_name, file_size))

    file_size_dl = 0
    block_sz = 8192
    while True:
        buffer = response.read(block_sz)
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


def build_command_configure(compiler_flags: CompileInfo, source_dir_path, prefix_path, executable='./configure'):
    # patches
    script_dir = os.path.dirname(source_dir_path)
    # +x for exec file
    st = os.stat(executable)
    os.chmod(executable, st.st_mode | stat.S_IEXEC)

    for file_names in compiler_flags.patches():
        scan_dir = os.path.join(script_dir, file_names)
        if os.path.exists(scan_dir):
            for diff in os.listdir(scan_dir):
                if re.match(r'.+\.patch', diff):
                    patch_file = os.path.join(scan_dir, diff)
                    line = 'patch -p0 < {0}'.format(patch_file)
                    subprocess.call(['bash', '-c', line])

    compile_cmd = [executable, '--prefix={0}'.format(prefix_path)]
    compile_cmd.extend(compiler_flags.flags())
    subprocess.call(compile_cmd)
    subprocess.call(['make', '-j2'])
    subprocess.call(['make', 'install'])
    if hasattr(shutil, 'which') and shutil.which('ldconfig'):
        subprocess.call(['ldconfig'])


def build_from_sources(url, compiler_flags: CompileInfo, source_dir_path, prefix_path, executable='./configure'):
    pwd = os.getcwd()
    file_path = download_file(url, pwd)
    extracted_folder = extract_file(file_path, pwd)
    os.chdir(extracted_folder)
    build_command_configure(compiler_flags, source_dir_path, prefix_path, executable)
    os.chdir(pwd)
    shutil.rmtree(extracted_folder)


def git_clone(url: str, current_dir: str, remove_dot_git=True):
    common_git_clone_line = ['git', 'clone', '--depth=1', url]
    cloned_dir = os.path.splitext(url.rsplit('/', 1)[-1])[0]
    common_git_clone_line.append(cloned_dir)
    subprocess.call(common_git_clone_line)
    os.chdir(cloned_dir)

    common_git_clone_init_line = ['git', 'submodule', 'update', '--init', '--recursive']
    subprocess.call(common_git_clone_init_line)
    directory = os.path.join(current_dir, cloned_dir)
    if remove_dot_git:
        shutil.rmtree(os.path.join(directory, '.git'))
    return directory

def git_clone_branch(url: str, branch: str, current_dir: str, remove_dot_git=True):
    common_git_clone_line = ['git', 'clone', '-b', branch, '--single-branch', '--depth=1', url]
    cloned_dir = os.path.splitext(url.rsplit('/', 1)[-1])[0]
    common_git_clone_line.append(cloned_dir)
    subprocess.call(common_git_clone_line)
    os.chdir(cloned_dir)

    common_git_clone_init_line = ['git', 'submodule', 'update', '--init', '--recursive']
    subprocess.call(common_git_clone_init_line)
    directory = os.path.join(current_dir, cloned_dir)
    if remove_dot_git:
        shutil.rmtree(os.path.join(directory, '.git'))
    return directory

def symlink_force(target, link_name):
    try:
        os.symlink(target, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(target, link_name)
        else:
            raise e
