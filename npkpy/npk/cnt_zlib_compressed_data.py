import struct
import zlib
from npkpy.npk.cnt_basic import CntBasic

NPK_ZLIB_COMPRESSED_DATA = 4


class CntZlibDompressedData(CntBasic):
    __decompressor = None
    __decompressed = None

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

    @property
    def output_cnt(self):
        id_name, options = super().output_cnt
        return id_name, options + [f"Uncompressed len: {len(self.get_cnt_payload_decompressed())}",
                                   f"Full decompress:  {self.decompressor.eof}",
                                   f"Non-decompressed tail length: {len(self.decompressor.unused_data)}"]
