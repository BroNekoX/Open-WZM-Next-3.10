| # | 3.10 vaddr | file off | 首指令 | 用途（日志事件/注释） | 反汇编 |
|---|---|---|---|---|---|
| 1 | 0x51f008 | 0x51f008 | 0x2f6c6464 | helmet-rule-direct-ddl-installed |  |
| 2 | 0xf28f20 | 0xf27f20 | 0xa9be7bfd | mobile-loot-table-alias | stp x29, x30, [sp, #-0x20]! ; str x19, [sp, #0x10] ; mov x29, sp |
| 3 | 0x118ca08 | 0x118ba08 | 0xd00260a0 | equip. Submit a copy with the gun descriptor through normal  | adrp x0, #0x5da2000 ; add x0, x0, #0xdb8 ; ret |
| 4 | 0x119e908 | 0x119d908 | 0xd10143ff | local-match-lobby-created | sub sp, sp, #0x50 ; stp x29, x30, [sp, #0x10] ; stp x24, x23, [sp, #0x20] |
| 5 | 0x12ee484 | 0x12ed484 | 0x14000002 | caller temporarily suppresses normal Interceptor callbacks. | b #0x12ee48c ; mov x19, xzr ; mov w8, #0xfd90 |
| 6 | 0x134febc | 0x134eebc | 0x3100041f | caller temporarily suppresses normal Interceptor callbacks. | cmn w0, #1 ; b.eq #0x134ff18 ; stp x29, x30, [sp, #-0x20]! |
| 7 | 0x14434a4 | 0x14424a4 | 0xd10283ff | helmet-rule-direct-ddl-installed | sub sp, sp, #0xa0 ; stp x29, x30, [sp, #0x40] ; stp x28, x27, [sp, #0x50] |
| 8 | 0x1443974 | 0x1442974 | 0xd10503ff | match-engine-error | sub sp, sp, #0x140 ; stp x29, x30, [sp, #0x100] ; stp x28, x23, [sp, #0x110] |
| 9 | 0x145c3ac | 0x145b3ac | 0xa9be7bfd | equip. Submit a copy with the gun descriptor through normal  | stp x29, x30, [sp, #-0x20]! ; stp x20, x19, [sp, #0x10] ; mov x29, sp |
| 10 | 0x145c9f0 | 0x145b9f0 | 0xd10383ff | local-match-lobby-created | sub sp, sp, #0xe0 ; stp x29, x30, [sp, #0x80] ; str x27, [sp, #0x90] |
| 11 | 0x1f64688 | 0x1f63688 | 0x3607f4c0 | caller temporarily suppresses normal Interceptor callbacks. | tbz w0, #0, #0x1f64520 ; mov w1, #4 ; mov w0, w23 |
| 12 | 0x20077a0 | 0x20067a0 | 0xa9be7bfd | helmet-rule-direct-ddl-installed | stp x29, x30, [sp, #-0x20]! ; str x19, [sp, #0x10] ; mov x29, sp |
| 13 | 0x20093ac | 0x20083ac | 0xa9bc7bfd | helmet-rule-direct-ddl-installed | stp x29, x30, [sp, #-0x40]! ; stp x24, x23, [sp, #0x10] ; stp x22, x21, [sp, #0x20] |
| 14 | 0x20e5690 | 0x20e4690 | 0xd10183ff | equip. Submit a copy with the gun descriptor through normal  | sub sp, sp, #0x60 ; stp x29, x30, [sp, #0x30] ; str x21, [sp, #0x40] |
| 15 | 0x2595250 | 0x2594250 | 0xaa0003f7 | reserving ID zero. It also detects resets after a mode chang | mov x23, x0 ; cbz x0, #0x2595368 ; mov w8, #7 |
| 16 | 0x259afc4 | 0x2599fc4 | 0xd10183ff | Every patched site must reach both ends of the arena with a  | sub sp, sp, #0x60 ; stp x29, x30, [sp, #0x20] ; str x23, [sp, #0x30] |
| 17 | 0x259b634 | 0x259a634 | 0xd10143ff | caller temporarily suppresses normal Interceptor callbacks. | sub sp, sp, #0x50 ; stp x29, x30, [sp, #0x10] ; str x23, [sp, #0x20] |
| 18 | 0x259ba18 | 0x259aa18 | 0xd101c3ff | caller temporarily suppresses normal Interceptor callbacks. | sub sp, sp, #0x70 ; stp x29, x30, [sp, #0x20] ; str x25, [sp, #0x30] |
| 19 | 0x368f014 | 0x368e014 | 0xb40000a0 | helmet-rule-direct-ddl-installed | cbz x0, #0x368f028 ; ldr x8, [x0, #0x10] ; cbz x8, #0x368f028 |
| 20 | 0x368f138 | 0x368e138 | 0xa9be7bfd | helmet-rule-direct-ddl-installed | stp x29, x30, [sp, #-0x20]! ; str x19, [sp, #0x10] ; mov x29, sp |
| 21 | 0x368f390 | 0x368e390 | 0x52800023 | helmet-rule-direct-ddl-installed | mov w3, #1 ; b #0x3695348 ; mov w3, #1 |
| 22 | 0x3690334 | 0x368f334 | 0xa9bf7bfd | helmet-rule-direct-ddl-installed | stp x29, x30, [sp, #-0x10]! ; mov x29, sp ; ldr w8, [x0, #4] |
| 23 | 0x39c6bf8 | 0x39c5bf8 | 0xd100c3ff | allocating an intermediate engine string (which became inval | sub sp, sp, #0x30 ; stp x29, x30, [sp, #0x10] ; stp x20, x19, [sp, #0x20] |
| 24 | 0x3cf84c4 | 0x3cf74c4 | 0xfc190fe8 | Called by Lab when it creates a local lobby. Use the server' | str d8, [sp, #-0x70]! ; stp x29, x30, [sp, #0x10] ; stp x28, x27, [sp, #0x20] |
| 25 | 0x3ee98fc | 0x3ee88fc | 0xf00523e0 | Called by Lab when it creates a local lobby. Use the server' | adrp x0, #0xe368000 ; add x0, x0, #0xa20 ; ret |
| 26 | 0x3f97164 | 0x3f96164 | 0x90052b68 | Called by Lab when it creates a local lobby. Use the server' | adrp x8, #0xe503000 ; ldr x0, [x8, #0xe28] ; ret |
| 27 | 0x4070928 | 0x406f928 | 0xd10203ff | before any loot has added those weapons to the server's live | sub sp, sp, #0x80 ; stp x29, x30, [sp, #0x30] ; str x25, [sp, #0x40] |
| 28 | 0x4070b64 | 0x406fb64 | 0xfc190fe8 | for slots it placed in this private BR session. | str d8, [sp, #-0x70]! ; stp x29, x30, [sp, #0x10] ; stp x28, x27, [sp, #0x20] |
| 29 | 0x40789c0 | 0x40779c0 | 0xa9ba7bfd | Map-specific fixed-squad placement through the original serv | stp x29, x30, [sp, #-0x60]! ; stp x28, x27, [sp, #0x10] ; stp x26, x25, [sp, #0x20] |
| 30 | 0x407ff18 | 0x407ef18 | 0xa9bd7bfd | Map-specific fixed-squad placement through the original serv | stp x29, x30, [sp, #-0x30]! ; str x21, [sp, #0x10] ; stp x20, x19, [sp, #0x20] |
| 31 | 0x40a4a90 | 0x40a3a90 | 0xd10683ff | bot attacks against an already-downed player are rejected. | sub sp, sp, #0x1a0 ; str d8, [sp, #0x130] ; stp x29, x30, [sp, #0x140] |
| 32 | 0x40ab14c | 0x40aa14c | 0xa9bb7bfd | Called by Lab when it creates a local lobby. Use the server' | stp x29, x30, [sp, #-0x50]! ; str x25, [sp, #0x10] ; stp x24, x23, [sp, #0x20] |
| 33 | 0x40ee7c0 | 0x40ed7c0 | 0xd10383ff | Called by Lab when it creates a local lobby. Use the server' | sub sp, sp, #0xe0 ; stp x29, x30, [sp, #0x80] ; stp x28, x27, [sp, #0x90] |
| 34 | 0x458de38 | 0x458ce38 | 0xbd02cf80 | Original execution animation/transform functions are not rep | str s0, [x28, #0x2cc] ; b.eq #0x458df84 ; ldr w0, [x20, x21] |
| 35 | 0x45a3d08 | 0x45a2d08 | 0xa9bd7bfd | Called by Lab when it creates a local lobby. Use the server' | stp x29, x30, [sp, #-0x30]! ; str x21, [sp, #0x10] ; stp x20, x19, [sp, #0x20] |
| 36 | 0x45a4bfc | 0x45a3bfc | 0xa9bc7bfd | Called by Lab when it creates a local lobby. Use the server' | stp x29, x30, [sp, #-0x40]! ; stp x28, x23, [sp, #0x10] ; stp x22, x21, [sp, #0x20] |
| 37 | 0x45b9f58 | 0x45b8f58 | 0xd102c3ff | Called by Lab when it creates a local lobby. Use the server' | sub sp, sp, #0xb0 ; stp x29, x30, [sp, #0x70] ; stp x24, x23, [sp, #0x80] |
| 38 | 0x46c5720 | 0x46c4720 | 0xa9bd7bfd | Called by Lab when it creates a local lobby. Use the server' | stp x29, x30, [sp, #-0x30]! ; str x28, [sp, #0x10] ; stp x20, x19, [sp, #0x20] |
| 39 | 0x47d9c6c | 0x47d8c6c | 0xa9422009 | caller temporarily suppresses normal Interceptor callbacks. | ldp x9, x8, [x0, #0x20] ; sub x8, x8, x9 ; lsr x0, x8, #3 |
| 40 | 0x47d9c7c | 0x47d8c7c | 0xa9be7bfd | caller temporarily suppresses normal Interceptor callbacks. | stp x29, x30, [sp, #-0x20]! ; stp x20, x19, [sp, #0x10] ; mov x29, sp |
| 41 | 0x47dbd60 | 0x47dad60 | 0xd100c3ff | caller temporarily suppresses normal Interceptor callbacks. | sub sp, sp, #0x30 ; stp x29, x30, [sp, #0x10] ; stp x20, x19, [sp, #0x20] |
| 42 | 0x47dcb60 | 0x47dbb60 | 0xa9be7bfd | caller temporarily suppresses normal Interceptor callbacks. | stp x29, x30, [sp, #-0x20]! ; stp x20, x19, [sp, #0x10] ; mov x29, sp |
| 43 | 0x47dd3f4 | 0x47dc3f4 | 0xd10103ff | caller temporarily suppresses normal Interceptor callbacks. | sub sp, sp, #0x40 ; stp x29, x30, [sp, #0x10] ; stp x22, x21, [sp, #0x20] |
| 44 | 0x47ded18 | 0x47ddd18 | 0xa9be7bfd | caller temporarily suppresses normal Interceptor callbacks. | stp x29, x30, [sp, #-0x20]! ; stp x20, x19, [sp, #0x10] ; mov x29, sp |
| 45 | 0x56579d0 | 0x56559d0 | 0x00000000 | Called by Lab when it creates a local lobby. Use the server' | udf #0 ; udf #0 ; udf #0 |
| 46 | 0x5657e08 | 0x5655e08 | 0x00000000 | Map-specific fixed-squad placement through the original serv | udf #0 ; udf #0 ; udf #0 |
| 47 | 0x5657e70 | 0x5655e70 | 0x00000000 | Called by Lab when it creates a local lobby. Use the server' | udf #0 ; udf #0 ; udf #0 |
| 48 | 0x5657ea8 | 0x5655ea8 | 0x00000000 | Called by Lab when it creates a local lobby. Use the server' | udf #0 ; udf #0 ; udf #0 |
| 49 | 0x5658b98 | 0x5656b98 | 0x00000000 | equip. Submit a copy with the gun descriptor through normal  | udf #0 ; udf #0 ; udf #0 |
| 50 | 0x566a038 | 0x5668038 | 0x00000000 | Called by Lab when it creates a local lobby. Use the server' | udf #0 ; udf #0 ; udf #0 |
| 51 | 0x569b560 | 0x5698560 | 0x00000001 | helmet-rule-direct-ddl-installed | udf #1 ; udf #0 ; cbnz x23, #0x5633e30 |
| 52 | 0xb7e0958 | 0x0 |  | equip. Submit a copy with the gun descriptor through normal  |  |
| 53 | 0xc67fcb4 | 0x0 |  | reserving ID zero. It also detects resets after a mode chang |  |
| 54 | 0xc67fd58 | 0x0 |  | reserving ID zero. It also detects resets after a mode chang |  |
| 55 | 0xc6ffd60 | 0x0 |  | reserving ID zero. It also detects resets after a mode chang |  |
| 56 | 0xe0aabd0 | 0x0 |  | Called by Lab when it creates a local lobby. Use the server' |  |
