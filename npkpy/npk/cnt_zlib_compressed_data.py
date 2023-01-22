import logging
import struct
import zlib
from npkpy.npk.cnt_basic import CntBasic

NPK_ZLIB_COMPRESSED_DATA = 4


class CntZlibDompressedData(CntBasic):
    __decompressor = None
    __decompressed = None
    __obj_list = None

    @property
    def _regular_cnt_id(self):
        return NPK_ZLIB_COMPRESSED_DATA

    @property
    def decompressor(self):
        if not self.__decompressor:
            self.__decompressor = zlib.decompressobj()
        return self.__decompressor

    def get_cnt_payload_decompressed(self):
        if not self.__decompressed:
            self.__decompressed = self.decompressor.decompress(self.cnt_payload)
            self.__decompressor.flush()
        return self.__decompressed

    def set_cnt_payload_decompressed(self, payload, blocksize=0x8000, level=0):
        offset = 0
        # compression method magic
        buffer_out = b"\x78\x01"
        adler32 = zlib.adler32(b"")
        while (offset < len(payload)):
            buffer_in = payload[offset:(offset + blocksize)]
            if (len(buffer_in) == blocksize):
                # not-last-block-marker
                block = b"\x00"
                compressed = zlib.compress(buffer_in, level)
                # for in-steam block, no magic, no last-marker, no adler32 tail
                block += compressed[3:-4]
            else:
                compressed = zlib.compress(buffer_in, level)
                # for last block, no magic, no adler32 tail
                block = compressed[2:-4]
            # adler32 over all the compressed data blocks
            adler32 = zlib.adler32(compressed[7:-4],adler32)
            buffer_out += block
            offset += blocksize

        buffer_out += struct.pack(">L",adler32)
        self.cnt_payload = buffer_out
        # reset our obj cache
        self.__decompressor = None
        self.__decompressed = None
        self.__obj_list = None

    @property
    def output_cnt(self):
        id_name, options = super().output_cnt
        return id_name, options + [f"Uncompressed len: {len(self.get_cnt_payload_decompressed())}",
                                   f"Full decompress:  {self.decompressor.eof}",
                                   f"Non-decompressed tail length: {len(self.decompressor.unused_data)}"]

    @property
    def cnt_enumerate_obj(self):
        for index, obj in enumerate(self.cnt_obj_list):
            yield index, obj

    @property
    def cnt_obj_list(self):
        if not self.__obj_list:
            self.__obj_list = self.__parse_all_obj()
        return self.__obj_list

    def __parse_all_obj(self):
        lst = []
        offset = 0
        while (offset < len(self.get_cnt_payload_decompressed())):
            lst.append(self.__get_obj(offset))
            offset += lst[-1].full_len
        return lst

    def __get_obj(self, offset):
        data = self.get_cnt_payload_decompressed()[offset:]
        payload_len = struct.unpack_from("<L", data, 24)[0]
        name_len = struct.unpack_from("<H", data, 28)[0]
        obj_len = 30 + payload_len + name_len
        data = data[:obj_len]
        return CntZlibPackedObj(binary=data)

class CntZlibPackedObj():
    """
    |mo de|nu ll nu ll nu ll|c_ ti me st|a_ ti me st|
    |m_ ti me st|nu ll nu ll|le np ay ld|le nn|name[lenn]|payload[lenpayld]

    not sure which timestamp is which here
    """
    _data = None
    __min_length = 0x1e # name starts at offset 0x1e

    def __init__(self, binary=b""):
        self._data = bytearray(binary)
        self.__set_len()

    def __set_len(self):
        len_data = len(self._data)
        len_required_diff = self.__min_length - len_data
        if (len_required_diff > 0):
            self._data += b"\x00"*len_required_diff
            if (not len_data == 0):
                logging.info("zlib cnt obj data too short for header")
        else:
            len_needed = self.__min_length + self.payload_len + self.name_len
            len_diff = len_needed - len_data
            if (len_diff == 0):
                return
            if (len_diff > 0):
                self._data += b"\x00"*len_diff
                logging.info("zlib cnt obj data too short for name + payload")
            else:
                self._data = self._data[:len_needed]
                logging.info("zlib cnt obj data too long for name + payload")

    @property
    def obj_mode(self):
        """
        stat.S_IMODE gives the file permissions (octal and mask 0o777)
        stat.S_IFMT gives the file type (mask 0o70000)
        See stat.S_ISDIR()
        """
        return struct.unpack_from("<H", self._data, 0)[0]

    @obj_mode.setter
    def obj_mode(self, obj_mode):
        struct.pack_into("<H", self._data, 0, obj_mode)

    @property
    def zeroes_one(self):
        tmp_unpack = struct.unpack_from("<HHH", self._data, 2)
        if (tmp_unpack != (0,0,0)):
            logging.warning("unexpected data seen at offset 2")
        return tmp_unpack

    @property
    def timestamps(self):
        return struct.unpack_from("<LLL", self._data, 8)
        # create a timestamps class, which can print or take pretty timestamps...

    @timestamps.setter
    def timestamps(self, timestamps):
        struct.pack_into("<LLL", self._data, 8, *timestamps)

    @property
    def zeroes_two(self):
        return struct.unpack_from("<L", self._data, 20)[0]

    @property
    def payload_len(self):
        return struct.unpack_from("<L", self._data, 24)[0]

    @payload_len.setter
    def payload_len(self, payload_len):
        struct.pack_into("<L", self._data, 24, payload_len)
        self.__set_len()

    @property
    def name_len(self):
        return struct.unpack_from("<H", self._data, 28)[0]

    @name_len.setter
    def name_len(self, name_len):
        old_name_len = self.name_len
        if name_len == old_name_len:
            return
        packed_len = struct.pack("<H", name_len)
        tmp_data = self._data[0:28]
        tmp_data += packed_len
        if name_len < old_name_len:
            tmp_data += self._data[30:(30+name_len)]
        else:
            tmp_data += self._data[30:(30+old_name_len)]
            tmp_data += b"\x00"*(name_len - old_name_len)
        tmp_data += self._data[(30+old_name_len):]
        self._data = tmp_data

    @property
    def name(self):
        return struct.unpack_from(f"{self.name_len}s", self._data, 30)[0].decode()

    @name.setter
    def name(self, name):
        self.name_len = len(name)
        struct.pack_into(f"{self.name_len}s", self._data, 30, name.encode(encoding="ascii"))

    @property
    def payload(self):
        return struct.unpack_from(f"{self.payload_len}s", self._data, 30+self.name_len)[0]

    @payload.setter
    def payload(self, payload):
        payload = bytearray(payload)
        self.payload_len = len(payload)
        self.__set_len()
        struct.pack_into(f"{self.payload_len}s", self._data, 30+self.name_len, payload)

    @property
    def full_len(self):
        return len(self._data)

    @property
    def binary(self):
        return self._data

    @property
    def output_obj(self):
        return ([f"obj type: 0o{self.obj_mode:o}",
                 f"obj timestamps: {self.timestamps}",
                 f"obj payload len: {self.payload_len}",
                 f"obj name: {self.name}"])
