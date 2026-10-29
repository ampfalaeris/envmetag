#!/usr/bin/env python3
"""Extract a split zip (name.z01 .. name.zNN + name.zip) and verify each entry.

Reads the central directory from the final .zip part, maps each entry's
(disk number, local header offset) to an offset in the parts concatenated in
order, raw-inflates the entry, and checks the uncompressed size and CRC32
against the central directory. Exits non-zero on any mismatch.

Usage: splitzip_extract.py <path/to/name.zip> <outdir>
"""
import struct
import sys
import zlib
from pathlib import Path


def parts_for(zip_path):
    stem = zip_path.with_suffix("")
    parts = sorted(zip_path.parent.glob(stem.name + ".z[0-9][0-9]"))
    return parts + [zip_path]


def read_eocd(data):
    i = data.rfind(b"PK\x05\x06")
    if i < 0:
        sys.exit("no end-of-central-directory record")
    (_, disk, cd_disk, n_disk, n_total, cd_size, cd_off, _) = struct.unpack(
        "<IHHHHIIH", data[i:i + 22])
    zip64 = data.rfind(b"PK\x06\x06", 0, i)
    if zip64 >= 0:
        (_, _, _, _, disk, cd_disk, n_disk, n_total, cd_size, cd_off) = struct.unpack(
            "<IQHHIIQQQQ", data[zip64:zip64 + 56])
    return disk, cd_disk, n_total, cd_size, cd_off


def zip64_extra(extra, usize, csize, off):
    j = 0
    while j + 4 <= len(extra):
        hid, hlen = struct.unpack("<HH", extra[j:j + 4])
        body = extra[j + 4:j + 4 + hlen]
        if hid == 1:
            k = 0
            vals = []
            for v in (usize, csize, off):
                if v == 0xFFFFFFFF:
                    vals.append(struct.unpack("<Q", body[k:k + 8])[0])
                    k += 8
                else:
                    vals.append(v)
            return tuple(vals)
        j += 4 + hlen
    return usize, csize, off


def main():
    zip_path, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    parts = parts_for(zip_path)
    sizes = [p.stat().st_size for p in parts]
    starts = [sum(sizes[:k]) for k in range(len(sizes))]
    print("parts:", ", ".join(f"{p.name} ({s:,} B)" for p, s in zip(parts, sizes)))

    last = zip_path.read_bytes()
    _, cd_disk, n_total, cd_size, cd_off = read_eocd(last)
    with open(parts[cd_disk], "rb") as fh:
        fh.seek(cd_off)
        cd = fh.read(cd_size)

    ok = True
    p = 0
    for _ in range(n_total):
        (sig, _, _, flags, method, _, _, crc, csize, usize, nlen, xlen, clen,
         disk, _, _, off) = struct.unpack("<IHHHHHHIIIHHHHHII", cd[p:p + 46])
        if sig != 0x02014B50:
            sys.exit(f"bad central directory signature at {p}")
        name = cd[p + 46:p + 46 + nlen].decode()
        extra = cd[p + 46 + nlen:p + 46 + nlen + xlen]
        p += 46 + nlen + xlen + clen
        usize, csize, off = zip64_extra(extra, usize, csize, off)
        if name.endswith("/"):
            continue
        if method != 8 or flags & 1:
            sys.exit(f"{name}: unsupported method {method} / flags {flags:#x}")

        absoff = starts[disk] + off
        with _Concat(parts, starts, sizes) as cat:
            hdr = cat.read_at(absoff, 30)
            if hdr[:4] != b"PK\x03\x04":
                sys.exit(f"{name}: no local header at disk {disk} offset {off}")
            lnlen, lxlen = struct.unpack("<HH", hdr[26:30])
            pos = absoff + 30 + lnlen + lxlen
            d = zlib.decompressobj(-15)
            got_crc, got_size, left = 0, 0, csize
            out = outdir / Path(name).name
            with open(out, "wb") as fo:
                while left > 0:
                    chunk = cat.read_at(pos, min(left, 1 << 22))
                    pos += len(chunk)
                    left -= len(chunk)
                    buf = d.decompress(chunk)
                    got_crc = zlib.crc32(buf, got_crc)
                    got_size += len(buf)
                    fo.write(buf)
                buf = d.flush()
                got_crc = zlib.crc32(buf, got_crc)
                got_size += len(buf)
                fo.write(buf)
        match = got_crc == crc and got_size == usize and d.eof
        ok &= match
        print(f"{name}: size {got_size:,} (expected {usize:,}), "
              f"crc32 {got_crc:08x} (expected {crc:08x}), "
              f"stream end {d.eof} -> {'OK' if match else 'MISMATCH'}")
    return 0 if ok else 1


class _Concat:
    """Random access over the split parts as one byte stream."""

    def __init__(self, parts, starts, sizes):
        self.fhs = [open(q, "rb") for q in parts]
        self.starts, self.sizes = starts, sizes

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        for f in self.fhs:
            f.close()

    def read_at(self, pos, n):
        out = bytearray()
        for f, s, z in zip(self.fhs, self.starts, self.sizes):
            if n == 0:
                break
            if s <= pos < s + z:
                f.seek(pos - s)
                b = f.read(min(n, s + z - pos))
                out += b
                pos += len(b)
                n -= len(b)
        return bytes(out)


if __name__ == "__main__":
    sys.exit(main())
