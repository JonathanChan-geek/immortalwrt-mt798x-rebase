#!/usr/bin/env python3
"""Compile the actual patched query serializers with small OS/WEXT test doubles."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('driver', type=Path, help='prepared mt_wifi package directory')
    args = parser.parse_args()
    header = (args.driver / 'mt_wifi/embedded/include/oid.h').read_text()
    source = (args.driver / 'mt_wifi/embedded/common/wnm.c').read_text()
    structs = '\n'.join(re.search(r'struct GNU_PACKED ' + name + r' \{.*?\n\};', header, re.S).group()
                        for name in ('btm_query_data', 'wnm_event'))
    assert 'UCHAR btm_query[];' in structs and 'btm_query[0]' not in structs
    funcs = '\n'.join(re.search(r'^void ' + name + r'\(.*?^\}', source, re.M | re.S).group()
                      for name in ('wext_send_btm_query_event', 'wext_send_btm_query_event_newapi'))
    prelude = r'''
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t UCHAR;
typedef uint8_t UINT8;
typedef uint16_t UINT16;
typedef uint32_t UINT32;
typedef UCHAR *PUCHAR;
typedef void *PNET_DEV;
#define GNU_PACKED __attribute__((packed))
#define RT_WLAN_EVENT_CUSTOM 1
#define OID_802_11_WNM_BTM_QUERY 2
#define OID_802_11_WNM_EVENT 3
#define OID_802_11_WNM_EVT_BTM_QUERY 4
static unsigned allocations, sends, fail_alloc, wire_len, wire_oid;
static unsigned char wire[65536];
__attribute__((noinline)) static int os_alloc_mem(void *unused, UCHAR **buf, size_t n) {
    (void)unused; allocations++; *buf = fail_alloc ? NULL : malloc(n); return *buf ? 0 : -1;
}
static void os_free_mem(void *buf) { free(buf); }
static unsigned RtmpOsGetNetIfIndex(void *dev) { (void)dev; return 42; }
static void RtmpOSWrielessEventSend(void *dev, unsigned type, unsigned oid,
                                  void *mac, UCHAR *data, unsigned n) {
    (void)dev; (void)type; (void)mac;
    assert(n <= sizeof(wire)); memcpy(wire, data, n);
    wire_len = n; wire_oid = oid; sends++;
}
#define NdisZeroMemory(p, n) memset(p, 0, n)
/* Model the field-size condition that raised the kernel FORTIFY warning. */
#define memcpy(d,s,n) ({ size_t _n=(n), _field=__builtin_object_size(d,1); \
    assert(_field==(size_t)-1 || _n<=_field); __builtin_memcpy(d,s,_n); })
'''
    tests = r'''
_Static_assert(sizeof(struct btm_query_data)==14, "query ABI changed");
_Static_assert(offsetof(struct btm_query_data,btm_query)==14, "payload offset changed");
_Static_assert(sizeof(struct wnm_event)==2, "wrapper ABI changed");
static unsigned char payload[65536];
static const char peer[6] = {1,2,3,4,5,6};
static void run_case(unsigned wrapped, unsigned n, unsigned oom, unsigned accept) {
    allocations=sends=wire_len=0; fail_alloc=oom;
    if (wrapped) wext_send_btm_query_event_newapi(NULL,peer,(char *)payload,n);
    else wext_send_btm_query_event(NULL,peer,(char *)payload,n);
    if (!accept) { assert(sends==0); assert(allocations==(oom ? 1u : 0u)); return; }
    assert(sends==1 && allocations==1);
    unsigned offset=wrapped ? sizeof(struct wnm_event) : 0;
    struct btm_query_data *q=(void *)(wire+offset);
    assert(wire_len==offset+14+n && q->ifindex==42 && q->btm_query_len==n);
    assert(!memcmp(q->peer_mac_addr,peer,6) && !memcmp(q->btm_query,payload,n));
    assert(wire_oid==(wrapped ? OID_802_11_WNM_EVENT : OID_802_11_WNM_BTM_QUERY));
    if(wrapped) { struct wnm_event *e=(void *)wire; assert(e->event_len==14+n); }
}
int main(void) {
    for(unsigned i=0;i<sizeof(payload);i++) payload[i]=(unsigned char)i;
    for(unsigned wrapped=0;wrapped<2;wrapped++) {
        run_case(wrapped,0,0,1); run_case(wrapped,2,0,1); run_case(wrapped,64,0,1);
        run_case(wrapped,2,1,0);
        unsigned limit=wrapped ? 241 : 65521;
        run_case(wrapped,limit,0,1); run_case(wrapped,limit+1,0,0);
        run_case(wrapped,65535,0,0);
    }
    return 0;
}
'''
    with tempfile.TemporaryDirectory(prefix='ax6000-wnm-') as tmp:
        path = Path(tmp)
        (path / 'test.c').write_text(prelude + structs + funcs + tests)
        subprocess.run(['cc', '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined,address', '-fno-omit-frame-pointer',
                        str(path / 'test.c'), '-o', str(path / 'test')], check=True)
        subprocess.run([str(path / 'test')], check=True)
    print(json.dumps({'wnm_query_cases': 14, 'query_header_bytes': 14,
                      'wire_layout_preserved': True, 'allocation_and_length_failures_checked': True,
                      'scope': 'actual C serializers with host OS/WEXT doubles; not a device runtime test'}))


if __name__ == '__main__':
    main()
