"""严格使用Vivado CSV第二行的实际数制，不按界面显示属性猜测。"""
import csv
def read_capture(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);radix=next(reader)
        rows=[r for r in reader if r['Sample in Buffer'].isdigit()]
    bases={'HEX':16,'UNSIGNED':10,'SIGNED':10,'BIN':2,'BINARY':2,'OCTAL':8}
    return [{k:int(v,bases.get(radix.get(k,''),10)) for k,v in r.items()} for r in rows]
def column(row,prefix):
    return next(k for k in row if k.startswith(prefix))
