import sys, os

repo = sys.argv[1]

# 1. Remove assert(enable_brave_wallet) from brave_wallet/common/BUILD.gn
f1 = os.path.join(repo, "components/brave_wallet/common/BUILD.gn")
with open(f1, 'r') as f:
    c1 = f.read()
c1 = c1.replace("assert(enable_brave_wallet)", "# assert(enable_brave_wallet)")
with open(f1, 'w') as f:
    f.write(c1)

# 2. Force include mojom_java in build/android/BUILD.gn
f2 = os.path.join(repo, "build/android/BUILD.gn")
with open(f2, 'r') as f:
    lines = f.readlines()
with open(f2, 'w') as f:
    skip = False
    for line in lines:
        if "if (enable_brave_wallet) {" in line and "mojom_java" in "".join(lines):
            pass # we need a better replacement
