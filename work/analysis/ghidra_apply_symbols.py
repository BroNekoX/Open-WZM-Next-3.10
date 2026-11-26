# Ghidra Jython: apply recovered names from libgame_310.symbols
# Run with: Script Manager -> Python (Jython) -> pick this file
from ghidra.program.model.symbol import SourceType
from java.io import File

PATH = r"E:\\Administrator\\Documents\\project\\wzm\\work\\analysis\\libgame_310.symbols"
cur = currentProgram
st = cur.getSymbolTable()
space = cur.getAddressFactory().getDefaultAddressSpace()
count = 0
for line in open(PATH):
    line = line.split("#")[0].strip()
    if not line:
        continue
    try:
        addr_s, name = line.split()
    except ValueError:
        continue
    a = space.getAddress(int(addr_s, 16))
    try:
        st.createLabel(a, name, SourceType.USER_DEFINED)
        count += 1
    except Exception as ex:
        print("skip", addr_s, name, ex)
print("applied %d labels" % count)
