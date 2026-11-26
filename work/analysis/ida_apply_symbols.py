"""IDAPython: apply recovered names from libgame_310.symbols."""
import idaapi, ida_name

PATH = r"E:\\Administrator\\Documents\\project\\wzm\\work\\analysis\\libgame_310.symbols"
for line in open(PATH, encoding="utf-8"):
    line = line.split("#")[0].strip()
    if not line or line.startswith("0x0") and " " not in line:
        continue
    try:
        addr_s, name = line.split()
        addr = int(addr_s, 16)
    except ValueError:
        continue
    if addr == idaapi.BADADDR:
        continue
    try:
        ida_name.set_name(addr, name, ida_name.SN_NOCHECK | ida_name.SN_FORCE)
    except Exception as ex:
        print("skip", hex(addr), name, ex)
print("done")
