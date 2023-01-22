import argparse
from pprint import pprint
import stat
import struct

from pathlib import Path

from npkpy.npk.npk import Npk, EmptyNpk
from npkpy.npk.cnt_zlib_compressed_data import NPK_ZLIB_COMPRESSED_DATA, CntZlibDompressedData, CntZlibPackedObj
from npkpy.npk.cnt_null_block import NPK_NULL_BLOCK, CntNullBlock
from npkpy.npk.cnt_squasfs_image import NPK_SQUASH_FS_IMAGE, CntSquashFsImage

def parse_args():
    parser = argparse.ArgumentParser(description='packing tool for Mikrotik NPK')
    parser.add_argument('--kernel', type=Path, default=Path("kernel.elf"),
                        help="The ELF boot file to pack into an NPK")
    parser.add_argument('--output', type=Path, default=Path("packed.npk"),
                        help="The filename of the resulting NPK")
    return parser.parse_args()

def print_overview(npk):
    print("----Overview--------------------")
    pprint([f"pos: {pos:2} - Name: {cnt.cnt_id_name} (id:{cnt.cnt_id:2}) cnt size 0x{cnt.cnt_full_length:x}" for pos, cnt in npk.pck_enumerate_cnt])
    print("pkg len:          ", npk.pck_payload_len)
    print("-------------------------------")

def pack_kernel():
    opts = parse_args()

    new_npk_file = EmptyNpk()

    kernel_elf = opts.kernel

    fp = open(kernel_elf,"rb")
    zlib_kernel_payload = fp.read()
    fp.close()

    outname = opts.output

    # squashfs container
    squash_cnt_bytes = b""
    squash_cnt_bytes += struct.pack(b"h", NPK_SQUASH_FS_IMAGE)
    squash_cnt_bytes += struct.pack(b"I", 0)

    squash_cnt = new_npk_file.cnt_bytes_to_cnt(squash_cnt_bytes)
    # squashfs _needs_ a payload, or RouterBOOT will not parse
    squash_cnt.cnt_payload = b"\x00"
    del squash_cnt_bytes
    new_npk_file.pck_cnt_list.append(squash_cnt)

    # zlib container
    zlib_cnt_bytes = b""
    zlib_cnt_bytes += struct.pack(b"h", NPK_ZLIB_COMPRESSED_DATA)
    zlib_cnt_bytes += struct.pack(b"I", 0)

    zlib_cnt = new_npk_file.cnt_bytes_to_cnt(zlib_cnt_bytes)
    del zlib_cnt_bytes
    new_npk_file.pck_cnt_list.append(zlib_cnt)

    mode_exec = stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH
    mode_reg = mode_exec & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    boot_obj = CntZlibPackedObj()
    boot_obj.obj_mode = stat.S_IFDIR | mode_exec
    boot_obj.name = "boot"
    kernel_obj = CntZlibPackedObj()
    kernel_obj.obj_mode = stat.S_IFREG | mode_exec
    kernel_obj.name = "boot/kernel"
    kernel_obj.payload = zlib_kernel_payload
    upgraded_obj = CntZlibPackedObj()
    upgraded_obj.obj_mode = stat.S_IFREG | mode_reg
    upgraded_obj.name = "UPGRADED"
    upgraded_obj.payload = b"\x00"*0x20

    objs_list = [boot_obj, kernel_obj, upgraded_obj]

    new_zlib_uncompressed = b""
    for index, obj in enumerate(objs_list):
        if (obj.name != "bin/bash"):
            new_zlib_uncompressed += obj.binary
    zlib_cnt.cnt_payload_decompressed = zlib_cnt.set_cnt_payload_decompressed(new_zlib_uncompressed, blocksize=0x8000)

    pprint([obj.output_obj for pos,obj in zlib_cnt.cnt_enumerate_obj])
    print_overview(new_npk_file)

    print(f"Write File: {outname}")
    Path(outname).write_bytes(new_npk_file.pck_full_binary)

if __name__ == '__main__':
    pack_kernel()
