from pprint import pprint
import struct

from npkpy.npk.npk import EmptyNpk


def create_poc():
    new_npk_file = EmptyNpk()

    extra_cnt_bytes = b""
    extra_cnt_bytes += struct.pack(b"h", 1)
    extra_cnt_bytes += struct.pack(b"I", 0)

    extra_cnt = new_npk_file.cnt_bytes_to_cnt(extra_cnt_bytes)
    extra_cnt.modified = True

    del extra_cnt_bytes

    new_npk_file.pck_cnt_list.append(extra_cnt)

    # print overview
    print("----Overview--------------------")
    pprint([f"pos: {pos:2} - Name: {cnt.cnt_id_name} (id:{cnt.cnt_id:2})" for pos, cnt in new_npk_file.pck_enumerate_cnt])
    print("pkg len:          ", new_npk_file.pck_payload_len)
    print("-------------------------------")

if __name__ == '__main__':
    create_poc()
