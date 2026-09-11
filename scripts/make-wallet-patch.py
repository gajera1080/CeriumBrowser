import os, sys, subprocess

repo = "/run/media/pc/D/brave-core"
os.chdir(repo)

# 1. components/brave_wallet/common/BUILD.gn
f = "components/brave_wallet/common/BUILD.gn"
with open(f, 'r') as fp: c = fp.read()
c = c.replace("assert(enable_brave_wallet)", "# assert(enable_brave_wallet)")
with open(f, 'w') as fp: fp.write(c)

# 2. build/android/config.gni
f = "build/android/config.gni"
with open(f, 'r') as fp: lines = fp.readlines()
with open(f, 'w') as fp:
    for line in lines:
        if "if (enable_brave_wallet)" in line:
            fp.write(line.replace("if (enable_brave_wallet)", "if (true)"))
        else:
            fp.write(line)

# 3. build/android/BUILD.gn
f = "build/android/BUILD.gn"
with open(f, 'r') as fp: lines = fp.readlines()
with open(f, 'w') as fp:
    for line in lines:
        if "if (enable_brave_wallet)" in line:
            fp.write(line.replace("if (enable_brave_wallet)", "if (true)"))
        else:
            fp.write(line)

# 4. android/BUILD.gn
f = "android/BUILD.gn"
with open(f, 'r') as fp: lines = fp.readlines()
with open(f, 'w') as fp:
    for line in lines:
        if "if (enable_brave_wallet)" in line:
            fp.write(line.replace("if (enable_brave_wallet)", "if (true)"))
        else:
            fp.write(line)

