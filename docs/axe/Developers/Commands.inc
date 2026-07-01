;#################################
;#    To Assembly Programmers    #
;#############################################################################################
;# This is a complete list of all the routines used when compiling programs from Axe Parser. #
;# Almost all of them are hand written by me and are highly optimized and sometimes hard to  #
;# follow, but if you see any optimizations for smaller size and faster code, please contact #
;# me so I can alter the routines to improve newer versions.  Conversely, everyone is free   #
;# to use these routines in their own programs and you don't need to credit me unless you    #
;# want to.                                                                                  #
;#############################################################################################

;No Operation
;-----------------------------------------------
p_NoOp:
	.db 0

;Headers
;-----------------------------------------------
p_AsmHeader:
	.db 2
	.dw $6DBB

p_IonHeader:
	.db 5
	.dw $6DBB
	xor	a
	jr	nc,$+0
	.db rp_Byte,1

p_MOSHeader:
	.db 34
	.dw $6DBB
	ret
	.db 1
	.db %00000001,%00000000
	.db %00011010,%10110000
	.db %00111110,%11111000
	.db %00111111,%11111000
	.db %00111111,%11111000
	.db %00111110,%11111000
	.db %00011010,%10110000
	.db %00001010,%10100000
	.db %00000010,%10000000
	.db %11111110,%11111110
	.db %11001101,%01000010
	.db %10110101,%01011110
	.db %10000110,%11000110
	.db %10110101,%01011110
	.db %10110101,%01000010

p_DCSHeader:
	.db 46
	.dw $6DBB
	xor d
	ret
	jr $+0
	.dw $9DC1
	.db $05,$00
	.dw $9DA1
	.dw $0000
	.db %00000001,%10000000
	.db %00011010,%01011000
	.db %00111110,%01111100
	.db %00111111,%11111100
	.db %00111111,%11111100
	.db %00111110,%01111100
	.db %00011010,%01011000
	.db %00001010,%01010000
	.db %00000010,%01000000
	.db %11111110,%01111111
	.db %11001101,%10100001
	.db %10110101,%10101111
	.db %10000110,%01100011
	.db %10110101,%10101111
	.db %10110101,%10100001
	.db %11111111,%11111111
	.db rp_Byte,41

p_APPHeader1:
	.db 18
	.db $80,$0F		;Field: Program length
	.db $00,$00,$00,$00	;Length=0 (N/A for unsigned apps)
	.db $80,$12		;Field: Program type
	.db $01,$04		;Type= Shareware, TI-83Plus
	.db $80,$21		;Field: App ID
	.db $01			;Id = 1
	.db $80,$31		;Field: App Build
	.db $01			;Build = 1
	.db $80,$48		;Field: App Name
;	.db "Name    "		;Name must be 8 characters
p_APPHeader2:
	.db p_APPHeaderEnd-p_APPHeader2-1
	.db $80,$81		;Field: App Pages
	.db $01			;App Pages = 1
	.db $80,$90		;No default splash screen
	.db $03,$26,$09,$04,$04,$6f,$1b,$80	;Field: Date stamp- 5/12/1999
	.db $02,$0d,$40		;Dummy encrypted TI date stamp signature
	.db $a1,$6b,$99,$f6,$59,$bc,$67
	.db $f5,$85,$9c,$09,$6c,$0f,$b4,$03,$9b,$c9
	.db $03,$32,$2c,$e0,$03,$20,$e3,$2c,$f4,$2d
	.db $73,$b4,$27,$c4,$a0,$72,$54,$b9,$ea,$7c
	.db $3b,$aa,$16,$f6,$77,$83,$7a,$ee,$1a,$d4
	.db $42,$4c,$6b,$8b,$13,$1f,$bb,$93,$8b,$fc
	.db $19,$1c,$3c,$ec,$4d,$e5,$75
	.db $80,$7F		;Field: Program Image length
	.db 0,0,0,0		;Length=0, N/A
	.db 0,0,0,0		;Reserved
	.db 0,0,0,0		;Reserved
	.db 0,0,0,0		;Reserved
	.db 0,0,0,0		;Reserved
	call $4000+p_APPHeaderEnd-p_APPHeader1+8-2
	B_CALL(_ReloadAppEntry)
	B_JUMP(_JForceCmdNoChar)
p_APPHeaderEnd:

p_AXSHeader:
	.db 57
	.db "Axe     "
	.db "Axe 1.22+ Needed",0
	ld	hl,$0000
	rst	20h
	push	hl
	B_CALL(_FindApp)		;(appSearchPage)=a, h=$40
	jr	c,__AXSHeader_NotFound
	ld	l,$10			;The next B_CALL calls $4010 in the app
	ld	(appSearchPage-2),hl	;  found. Axe 1.20+ has code embedded
#define App4010 appSearchPage-2+$4000	;  in the header to handle the rest of
	B_CALL(App4010)			;  the setup.
__AXSHeader_NotFound:			;Earlier versions of Axe return here
	B_CALL(_HomeUp)
	B_CALL(_ClrScrnFull)
	pop	hl
	B_CALL(_PutS)
	B_CALL(_GetKeyRetOff)
	ret
	.db rp_Ans,31

;Various Useful Micro-Operations
;-----------------------------------------------
p_LoadAnsHL:
	.db 3
	ld	hl,$0000
	.db rp_Ans,2
p_LoadAnsDE:
	.db 3
	ld	de,$0000
	.db rp_Ans,2
p_LoadAnsBC:
	.db 3
	ld	bc,$0000
	.db rp_Ans,2
p_LoadAnsIX:
	.db 4
	ld	ix,$0000
	.db rp_Ans,2
p_LoadAnsB:
	.db 2
	ld	b,0
	.db rp_Byte,1

p_LoadAns_HL_:
	.db 3
	ld	hl,($0000)
	.db rp_Ans,2
p_LoadAns_DE_:
	.db 4
	ld	de,($0000)
	.db rp_Ans,2
p_LoadAns_BC_:
	.db 4
	ld	bc,($0000)
	.db rp_Ans,2
p_LoadAns_A_:
	.db 3
	ld	a,($0000)
	.db rp_Ans,2
p_LoadAnsTiny:
	.db 5
	ld	hl,($0000)
	ld	h,0
	.db rp_Ans,4
p_LoadAnsTinyDE:
	.db 6
	ld	a,($0000)
	ld	e,a
	ld	d,0
	.db rp_Ans,5
p_LoadSwapDE:
	.db 6
	ld	bc,($0000)
	ld	e,b
	ld	d,c
	.db rp_Ans,4
p_SaveAns_HL_:
	.db 3
	ld	($0000),hl
	.db rp_Ans,2
p_SaveAns_DE_:
	.db 4
	ld	($0000),de
	.db rp_Ans,2
p_SaveAnsTiny:
	.db 4
	ld	a,l
	ld	($0000),a
	.db rp_Ans,2

p_PushHL:
	.db 1
	push	hl
p_PushDE:
	.db 1
	push	de
p_PushBC:
	.db 1
	push	bc
p_PopHL:
	.db 1
	pop	hl
p_PopDE:
	.db 1
	pop	de
p_PopBC:
	.db 1
	pop	bc

p_ExHLDE:
p_ExDEHL:
	.db 1
	ex	de,hl
p_LdHLCA:
	.db 2
	ld	h,c
	ld	l,a
p_LD_B_L:
	.db	1
	ld	b,l
p_HLintoIXPop:
	.db 3
	ex	(sp),hl
	pop	ix
p_HLintoIXPop2:
	.db 5
	push	hl
	pop	ix
	pop	de
	pop	hl
p_ExDEHLPopHL:
	.db 2
	ex	de,hl
	pop	hl

p_LdPtr:
	.db 3
	ld	l,(hl)
	ld	h,0
p_LdPtr2:
	.db 4
	ld	a,(hl)
	inc	hl
	ld	h,(hl)
	ld	l,a
p_LdPtrRev:
	.db 4
	ld	a,(hl)
	inc	hl
	ld	l,(hl)
	ld	h,a
p_SavePtr:
	.db 1
	ld	(hl),e
p_SavePtr2:
	.db 3
	ld	(hl),e
	inc	hl
	ld	(hl),d
p_SavePtrRev:
	.db 3
	ld	(hl),d
	inc	hl
	ld	(hl),e
p_LdSelf:
	.db 2
	ld	d,h
	ld	e,l
p_SwapHL:
	.db 3
	ld	a,h
	ld	h,l
	ld	l,a

p_IncByte:
	.db 1
	inc	(hl)
p_IncWord:
	.db 5
	inc	(hl)
	jr	nz,$+4
	inc	hl
	inc	(hl)
p_IncRev:
	.db 6
	inc	hl
	inc	(hl)
	jr	nz,$+4
	dec	hl
	inc	(hl)
p_IncRevConst:
	.db 8
	ld	hl,$0000
	inc	(hl)
	jr	nz,$+4
	dec	hl
	inc	(hl)
	.db rp_Ans,7
p_DecByte:
	.db 1
	dec	(hl)
p_DecWord:
	.db 7
	ld	a,(hl)
	dec	(hl)
	or	a
	jr	nz,$+4
	inc	hl
	dec	(hl)
p_DecRev:
	.db 7
	ld	d,(hl)
	inc	hl
	ld	e,(hl)
	dec	de
	ld	(hl),e
	dec	hl
	ld	(hl),d
p_DecRevConst:
	.db 10
	ld	hl,$0000
	ld	a,(hl)
	dec	(hl)
	or	a
	jr	nz,$+4
	dec	hl
	dec	(hl)
	.db rp_Ans,9

;Trivial Results
;-----------------------------------------------
p_False:
	.db 3
	ld	hl,0
p_True:
	.db 3
	ld	hl,1
p_MaxInt:
	.db 3
	ld	hl,$FFFF
p_ZeroH:
	.db 2
	ld	h,0
p_ZeroL:
	.db 2
	ld	l,0
p_MaxH:
	.db 2
	ld	h,$FF
p_MaxL:
	.db 2
	ld	l,$FF
p_ZeroD:
	.db 2
	ld	d,0

;Optimized Math
;-----------------------------------------------
p_Add1:
	.db 1
	inc	hl
p_Add2:
	.db 2
	inc	hl
	inc	hl
p_Add3:
	.db 3
	inc	hl
	inc	hl
	inc	hl
p_Add254:
	.db 3
	inc	h
	dec	hl
	dec	hl
p_Add255:
	.db 2
	inc	h
	dec	hl
p_Add256:
	.db 1
	inc	h
p_Add257:
	.db 2
	inc	h
	inc	hl
p_Add258:
	.db 3
	inc	h
	inc	hl
	inc	hl
p_Add510:
	.db 4
	inc	h
	inc	h
	dec	hl
	dec	hl
p_Add511:
	.db 3
	inc	h
	inc	h
	dec	hl
p_Add512:
	.db 2
	inc	h
	inc	h
p_Add513:
	.db 3
	inc	h
	inc	h
	inc	hl
p_Add514:
	.db 4
	inc	h
	inc	h
	inc	hl
	inc	hl
p_Add767:
	.db 4
	inc	h
	inc	h
	inc	h
	dec	hl
p_Add768:
	.db 3
	inc	h
	inc	h
	inc	h
p_Add769:
	.db 4
	inc	h
	inc	h
	inc	h
	inc	hl
p_Add1024:
	.db 4
	inc	h
	inc	h
	inc	h
	inc	h

p_Sub1024:
	.db 4
	dec	h
	dec	h
	dec	h
	dec	h
p_Sub769:
	.db 4
	dec	h
	dec	h
	dec	h
	dec	hl
p_Sub768:
	.db 3
	dec	h
	dec	h
	dec	h
p_Sub767:
	.db 4
	dec	h
	dec	h
	dec	h
	inc	hl
p_Sub514:
	.db 4
	dec	h
	dec	h
	dec	hl
	dec	hl
p_Sub513:
	.db 3
	dec	h
	dec	h
	dec	hl
p_Sub512:
	.db 2
	dec	h
	dec	h
p_Sub511:
	.db 3
	dec	h
	dec	h
	inc	hl
p_Sub510:
	.db 4
	dec	h
	dec	h
	inc	hl
	inc	hl
p_Sub258:
	.db 3
	dec	h
	dec	hl
	dec	hl
p_Sub257:
	.db 2
	dec	h
	dec	hl
p_Sub256:
	.db 1
	dec	h
p_Sub255:
	.db 2
	dec	h
	inc	hl
p_Sub254:
	.db 3
	dec	h
	inc	hl
	inc	hl
p_Sub3:
	.db 3
	dec	hl
	dec	hl
	dec	hl
p_Sub2:
	.db 2
	dec	hl
	dec	hl
p_Sub1:
	.db 1
	dec	hl
p_Mul2:
	.db 1
	add	hl,hl
p_Mul3:
	.db 4
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,de
p_Mul4:
	.db 2
	add	hl,hl
	add	hl,hl
p_Mul5:
	.db 5
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,hl
	add	hl,de
p_Mul6:
	.db 5
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,de
	add	hl,hl
p_Mul7:
	.db 6
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,de
	add	hl,hl
	add	hl,de
p_Mul8:
	.db 3
	add	hl,hl
	add	hl,hl
	add	hl,hl
p_Mul9:
	.db 6
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,de
p_Mul10:
	.db 6
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,hl
	add	hl,de
	add	hl,hl
p_Mul12:
	.db 6
	ld	d,h
	ld	e,l
	add	hl,hl
	add	hl,de
	add	hl,hl
	add	hl,hl
p_Mul16:
	.db 4
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
p_Mul32:
	.db 5
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
p_Mul64:
	.db 6
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	hl,hl
p_Mul128:
	.db 5
	ld	b,7
	add	hl,hl
	djnz	$-1
p_Mul255:
	.db 6
	ex	de,hl
	ld	h,e
	xor	a
	ld	l,a
	sbc	hl,de
p_Mul256:
	.db 3
	ld	h,l
	ld	l,0
p_Mul257:
	.db 3
	ld	a,l
	add	a,h
	ld	h,a
p_Mul258:
	.db 4
	ld	a,l
	add	hl,hl
	add	a,h
	ld	h,a
p_Mul260:
	.db 5
	ld	a,l
	add	hl,hl
	add	hl,hl
	add	a,h
	ld	h,a
p_Mul264:
	.db 6
	ld	a,l
	add	hl,hl
	add	hl,hl
	add	hl,hl
	add	a,h
	ld	h,a
p_Mul512:
	.db 4
	ld	h,l
	ld	l,0
	add	hl,hl
p_Mul513:
	.db 6
	ex	de,hl
	ld	h,e
	ld	l,0
	add	hl,hl
	add	hl,de
p_Mul514:
	.db 4
	ld	a,l
	add	a,h
	ld	h,a
	add	hl,hl
p_Mul516:
	.db 5
	ld	a,l
	add	hl,hl
	add	a,h
	ld	h,a
	add	hl,hl
p_Mul520:
	.db 6
	ld	a,l
	add	hl,hl
	add	hl,hl
	add	a,h
	ld	h,a
	add	hl,hl
p_Mul768:
	.db 6
	ld	a,l
	add	a,a
	add	a,l
	ld	h,a
	ld	l,0
p_Mul1024:
	.db 5
	ld	h,l
	ld	l,0
	add	hl,hl
	add	hl,hl
p_Mul1028:
	.db 5
	ld	a,l
	add	a,h
	ld	h,a
	add	hl,hl
	add	hl,hl
p_Mul1032:
	.db 6
	ld	a,l
	add	hl,hl
	add	a,h
	ld	h,a
	add	hl,hl
	add	hl,hl
p_Mul2048:
	.db 6
	ld	h,l
	ld	l,0
	add	hl,hl
	add	hl,hl
	add	hl,hl
p_Mul2056:
	.db 6
	ld	a,l
	add	a,h
	ld	h,a
	add	hl,hl
	add	hl,hl
	add	hl,hl
p_Mul4096:
	.db 6
	ld	b,12/2
	add	hl,hl
	add	hl,hl
	djnz	$-2
p_Mul8192:
	.db 5
	ld	b,13
	add	hl,hl
	djnz	$-1
p_Mul16384:
	.db 6
	ld	b,14/2
	add	hl,hl
	add	hl,hl
	djnz	$-2
p_Mul32768:
	.db 6
	xor	a
	rr	l
	ld	l,a
	rra
	ld	h,a
p_Div2:
	.db 4
	srl	h
	rr	l
p_Div10:
	.db 3
	B_CALL(_DivHLBy10)
p_Div128:
	.db 5
	xor	a
	add	hl,hl
	rla
	ld	l,h
	ld	h,a
p_Div256:
	.db 3
	ld	l,h
	ld	h,0
p_Div512:
	.db 5
	ld	l,h
	ld	h,0
	srl	l
p_Div32768:
	.db 5
	xor	a
	add	hl,hl
	ld	h,a
	rla
	ld	l,a
p_SDiv0:
	.db 6
	add	hl,hl
	sbc	a,a
	cpl
	ld	l,a
	rra
	ld	h,a
p_SDiv2:
	.db 4
	sra	h
	rr	l
p_SDiv64:
	.db 6
	add	hl,hl
	sbc	a,a
	add	hl,hl
	rla
	ld	l,h
	ld	h,a
p_SDiv128:
	.db 4
	add	hl,hl
	sbc	a,a
	ld	l,h
	ld	h,a
p_SDiv256:
	.db 5
	ld	a,h
	rla
	sbc	a,a
	ld	l,h
	ld	h,a
p_SDiv512:
	.db 6
	ld	a,h
	add	hl,hl
	sbc	hl,hl
	rra
	ld	l,a
p_SDiv16384:
	.db 6
	add	hl,hl
	sbc	a,a
	add	hl,hl
	ld	h,a
	rla
	ld	l,a
p_SDiv32768:
	.db 3
	add	hl,hl
	sbc	hl,hl
p_Mod2:
	.db 5
	xor	a
	ld	h,a
	inc	a
	and	l
	ld	l,a
p_Mod4:
	.db 6
	ld	h,0
	ld	a,l
	and	%00000011
	ld	l,a
p_Mod8:
	.db 6
	ld	h,0
	ld	a,l
	and	%00000111
	ld	l,a
p_Mod10:
	.db 6
	B_CALL(_DivHLBy10)
	ld	h,0
	ld	l,a
p_Mod16:
	.db 6
	ld	h,0
	ld	a,l
	and	%00001111
	ld	l,a
p_Mod32:
	.db 6
	ld	h,0
	ld	a,l
	and	%00011111
	ld	l,a
p_Mod64:
	.db 6
	ld	h,0
	ld	a,l
	and	%00111111
	ld	l,a
p_Mod128:
	.db 4
	ld	h,0
	res	7,l
p_Mod256:
	.db 2
	ld	h,0
p_Mod512:
	.db 4
	ld	a,%00000001
	and	h
	ld	h,a
p_Mod1024:
	.db 4
	ld	a,%00000011
	and	h
	ld	h,a
p_Mod2048:
	.db 4
	ld	a,%00000111
	and	h
	ld	h,a
p_Mod4096:
	.db 4
	ld	a,%00001111
	and	h
	ld	h,a
p_Mod8192:
	.db 4
	ld	a,%00011111
	and	h
	ld	h,a
p_Mod16384:
	.db 4
	ld	a,%00111111
	and	h
	ld	h,a
p_Mod32768:
	.db 2
	res	7,h
p_EQN512:
	.db 9
	inc	h
	inc	h
	ld	a,l
	and	h
	sub	255
	sbc	hl,hl
	inc	hl
p_EQN256:
	.db 8
	inc	h
	ld	a,l
	and	h
	sub	255
	sbc	hl,hl
	inc	hl
p_EQN2:
	.db 8
	inc	l
	ld	a,l
	and	h
	sub	255
	sbc	hl,hl
	inc	hl
p_EQN1:
	.db 7
	ld	a,l
	and	h
	sub	255
	sbc	hl,hl
	inc	hl
p_EQ0:
	.db 7
	ld	a,l
	or	h
	add	a,255
	sbc	hl,hl
	inc	hl
p_EQ1:
	.db 7
	ld	a,l
	dec	a
	or	h
	jr	z,$+4
	sbc	hl,hl
p_EQ2:
	.db 8
	dec	l
	ld	a,l
	dec	a
	or	h
	jr	z,$+4
	sbc	hl,hl
p_EQ256:
	.db 8
	dec	h
	ld	a,l
	or	h
	add	a,255
	sbc	hl,hl
	inc	hl
p_EQ512:
	.db 9
	dec	h
	dec	h
	ld	a,l
	or	h
	add	a,255
	sbc	hl,hl
	inc	hl
p_NEN512:
	.db 9
	inc	h
	inc	h
	ld	a,l
	or	h
	jr	z,$+5
	ld	hl,1
p_NEN256:
	.db 8
	inc	h
	ld	a,l
	or	h
	jr	z,$+5
	ld	hl,1
p_NEN2:
	.db 8
	inc	l
	ld	a,l
	and	h
	add	a,1
	sbc	hl,hl
	inc	hl
p_NEN1:
	.db 7
	ld	a,l
	and	h
	add	a,1
	sbc	hl,hl
	inc	hl
p_NE0:
	.db 7
	ld	a,l
	or	h
	jr	z,$+5
	ld	hl,1
p_NE1:
	.db 8
	ld	a,h
	dec	l
	or	l
	jr	z,$+5
	ld	hl,1
p_NE2:
	.db 9
	ld	a,h
	dec	l
	dec	l
	or	l
	jr	z,$+5
	ld	hl,1
p_NE256:
	.db 8
	dec	h
	ld	a,l
	or	h
	jr	z,$+5
	ld	hl,1
p_NE512:
	.db 9
	dec	h
	dec	h
	ld	a,l
	or	h
	jr	z,$+5
	ld	hl,1
p_GE1 =p_NE0
p_GT0 =p_GE1
p_GE256:
	.db 6
	ld	a,h
	sub	1
	sbc	hl,hl
	inc	hl
p_GT255 =p_GE256
p_LT1 =p_EQ0
p_LE0 =p_LT1
p_LT256:
	.db 6
	ld	a,h
	add	a,255
	sbc	hl,hl
	inc	hl
p_LE255 =p_LT256
p_SGE0:
	.db 4
	add	hl,hl
	sbc	hl,hl
	inc	hl
p_SLT0 =p_Div32768
p_GetBit0 =p_Div32768
p_GetBit1:
	.db 6
	xor	a
	add	hl,hl
	add	hl,hl
	ld	h,a
	rla
	ld	l,a
p_GetBit2:
	.db 7
	ld	a,h
	set	5,h
	cp	h
	sbc	hl,hl
	inc	hl
p_GetBit3:
	.db 7
	ld	a,h
	set	4,h
	cp	h
	sbc	hl,hl
	inc	hl
p_GetBit4:
	.db 7
	ld	a,h
	set	3,h
	cp	h
	sbc	hl,hl
	inc	hl
p_GetBit5:
	.db 7
	ld	a,h
	set	2,h
	cp	h
	sbc	hl,hl
	inc	hl
p_GetBit6:
	.db 7
	ld	a,%00000010
	and	h
	rrca
	ld	h,0
	ld	l,a
p_GetBit7:
	.db 6
	ld	a,%00000001
	and	h
	ld	h,0
	ld	l,a
p_GetBit8:
	.db 5
	xor	a
	ld	h,a
	add	hl,hl
	ld	l,h
	ld	h,a
p_GetBit9:
	.db 6
	xor	a
	add	hl,hl
	ld	h,a
	add	hl,hl
	ld	l,h
	ld	h,a
p_GetBit10:
	.db 7
	ld	a,l
	set	5,l
	cp	l
	sbc	hl,hl
	inc	hl
p_GetBit11:
	.db 7
	ld	a,l
	set	4,l
	cp	l
	sbc	hl,hl
	inc	hl
p_GetBit12:
	.db 7
	ld	a,l
	set	3,l
	cp	l
	sbc	hl,hl
	inc	hl
p_GetBit13:
	.db 7
	ld	a,l
	set	2,l
	cp	l
	sbc	hl,hl
	inc	hl
p_GetBit14:
	.db 7
	ld	a,%00000010
	and	l
	rrca
	ld	h,0
	ld	l,a
p_GetBit15 =p_Mod2

;Comparing numbers
;-----------------------------------------------
p_IntEq:
	.db 8
	xor	a
	sbc	hl,de
	ld	h,a
	ld	l,a
	jr	nz,$+3
	inc	l
p_IntNe:
	.db 8
	xor	a
	sbc	hl,de
	jr	z,$+5
	ld	hl,1
p_IntGt:
	.db 6
	scf
	sbc	hl,de
	sbc	hl,hl
	inc	hl
p_IntGe:
	.db 6
	or	a
	sbc	hl,de
	sbc	hl,hl
	inc	hl
p_IntLt:
	.db 6
	xor	a
	sbc	hl,de
	ld	h,a
	rla
	ld	l,a
p_IntLe:
	.db 7
	ex	de,hl
	or	a
	sbc	hl,de
	sbc	hl,hl
	inc	hl
p_EqX:
	.db 9
	ld	a,l
	sub	$00
	or	h
	add	a,255
	sbc	hl,hl
	inc	hl
	.db rp_Byte,7
p_EqNX:
	.db 9
	ld	a,l
	sub	$00
	and	h
	sub	255
	sbc	hl,hl
	inc	hl
	.db rp_Byte,7
p_NeX:
	.db 9
	ld	a,l
	sub	$00
	or	h
	sub	1
	sbc	hl,hl
	inc	hl
	.db rp_Byte,7
p_NeNX:
	.db 9
	ld	a,l
	sub	$00
	and	h
	add	a,1
	sbc	hl,hl
	inc	hl
	.db rp_Byte,7
p_LtLeXX:
	.db	7
	ld	de,$0000
	add	hl,de
	sbc	hl,hl
	inc	hl
	.db rp_Ans,6
p_GtGeXX:
	.db	8
	xor	a
	ld	de,$0000
	add	hl,de
	ld	h,a
	rla
	ld	l,a
	.db rp_Ans,6
p_Min:
	.db 7
	ld	a,l
	sub	e
	ld	a,h
	sbc	a,d
	jr	c,$+3
	ex	de,hl
p_Max:
	.db 7
	ld	a,l
	sub	e
	ld	a,h
	sbc	a,d
	jr	nc,$+3
	ex	de,hl

;Signed Comparisons
;-----------------------------------------------
p_SIntGt:
	.db 12
	ld	a,l
	scf
	sbc	a,e
	ld	a,h
	sbc	a,d
	rra
	xor	d
	xor	h
	rla
	sbc	hl,hl
	inc	hl
p_SIntGe:
	.db 11
	ld	a,l
	sub	e
	ld	a,h
	sbc	a,d
	rra
	xor	d
	xor	h
	rla
	sbc	hl,hl
	inc	hl
p_SIntLt:
	.db 12
	xor	a
	ld	b,h
	sbc	hl,de
	ld	h,a
	rra
	xor	b
	xor	d
	rlca
	and	1
	ld	l,a
p_SIntLe:
	.db 11
	ld	a,e
	sub	l
	ld	a,d
	sbc	a,h
	rra
	xor	d
	xor	h
	rla
	sbc	hl,hl
	inc	hl
p_SMin:
	.db	11
	ld	a,l
	sub	e
	ld	a,h
	sbc	a,d
	rra
	xor	d
	xor	h
	jp	m,$+4
	ex	de,hl
	.db rp_Ans,3
p_SMax:
	.db	11
	ld	a,l
	sub	e
	ld	a,h
	sbc	a,d
	rra
	xor	d
	xor	h
	jp	p,$+4
	ex	de,hl
	.db rp_Ans,3

;Basic Arithmetic
;-----------------------------------------------
p_Add:
	.db 1
	add	hl,de
p_Sub:
	.db 3
	or	a
	sbc	hl,de
p_IntNeg:
	.db 6
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
p_AbsInt:
	.db 10
	bit	7,h
	jr	z,$+8
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
p_MiniSigned:
	.db 5
	ld	a,(hl)
	ld	l,a
	rlca
	sbc	a,a
	ld	h,a

;Bit Operations
;-----------------------------------------------
p_IntOr:
	.db 6
	ld	a,h
	or	d
	ld	h,a
	ld	a,l
	or	e
	ld	l,a
p_IntAnd:
	.db 6
	ld	a,h
	and	d
	ld	h,a
	ld	a,l
	and	e
	ld	l,a
p_IntXor:
	.db 6
	ld	a,h
	xor	d
	ld	h,a
	ld	a,l
	xor	e
	ld	l,a
p_IntNot:
	.db 6
	ld	a,h
	cpl
	ld	h,a
	ld	a,l
	cpl
	ld	l,a
p_IntOrX:
	.db 4
	ld	a,h
	or	$00
	ld	h,a
	.db rp_Byte,2
p_IntAndX:
	.db 4
	ld	a,h
	and	$00
	ld	h,a
	.db rp_Byte,2
p_IntXorX:
	.db 4
	ld	a,h
	xor	$00
	ld	h,a
	.db rp_Byte,2
p_BoolOr:
	.db 3
	ld	a,l
	or	e
	ld	l,a
p_BoolAnd:
	.db 3
	ld	a,l
	and	e
	ld	l,a
p_BoolXor:
	.db 3
	ld	a,l
	xor	e
	ld	l,a
p_BoolNot:
	.db 3
	ld	a,l
	cpl
	ld	l,a
p_BoolNot2:
	.db 3
	ld	a,h
	cpl
	ld	h,a
p_BoolOrX:
	.db 4
	ld	a,l
	or	$00
	ld	l,a
	.db rp_Byte,2
p_BoolAndX:
	.db 4
	ld	a,l
	and	$00
	ld	l,a
	.db rp_Byte,2
p_BoolXorX:
	.db 4
	ld	a,l
	xor	$00
	ld	l,a
	.db rp_Byte,2

;Control And Program Flow
;-----------------------------------------------
p_Jp:
	.db 3
	jp	$0000
	.db rp_Ans,2
p_Jr:
	.db 2
	jr	$+0
	.db rp_Byte,1
p_Jpz:
	.db 3
	jp	z,$0000
	.db rp_Ans,2
p_Jrz:
	.db 2
	jr	z,$+0
	.db rp_Byte,1
p_Jpnz:
	.db 3
	jp	nz,$0000
	.db rp_Ans,2
p_Jrnz:
	.db 2
	jr	nz,$+0
	.db rp_Byte,1
p_djnz:
	.db 2
	djnz	$+0
	.db rp_Byte,1

p_CheckHLZero:
	.db 2
	ld	a,h
	or	l

p_JumpHL:
	.db 1
	jp	(hl)
p_CallHL:
	.db 6
	pop	ix
	ex	(sp),ix
	jp	(ix)
p_JpSymbol:
	.db 3
	jp	$0000
	.db rp_Sym,2
p_JpzSymbol:
	.db 3
	jp	z,$0000
	.db rp_Sym,2
p_JpnzSymbol:
	.db 3
	jp	nz,$0000
	.db rp_Sym,2
p_JpCpHLDE:
	.db 6
	or	a
	sbc	hl,de
	jp	c,$0000
	.db rp_Sym,2
p_Switch:
	.db __SwitchEnd-$-1
;	ld	bc,jumptable_end
;	ld	de,-range
	add	hl,de
	ret	c
	add	hl,hl
	add	hl,bc
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	ex	de,hl
	ex	(sp),hl
	ret
__SwitchEnd:

p_Call:
	.db 3
	call	$0000
	.db rp_Ans,2
p_CallSymbol:
	.db 3
	call	$0000
	.db rp_Sym,2

p_Ret:
	.db 1
	ret
p_Retnz:
	.db 1
	ret	nz
p_Retz:
	.db 1
	ret	z
p_SkipNext4:
	.db 2
	jr	$+6
p_RetInstant:
	.db 7
	ld	hl,(errSP)
	dec	hl
	dec	hl
	ld	sp,hl
	ret
p_RetApp:
	.db 3
	jp	$4083
p_RetFrame:
	.db 9
	ld	hl,(errSP)
	ld	de,-6
	add	hl,de
	ld	sp,hl
	ret
p_DecB:
	.db 1
	dec	b
p_DecC:
	.db 1
	dec	c

p_ForConvert:
	.db 5
	dec	hl
	ld	b,l
	ld	c,h
	inc	b
	inc	c

;Data Manipulation
;-----------------------------------------------
p_Fill:
	.db 7
	ex	(sp),hl
	pop	bc
	ld	d,h
	ld	e,l
	inc	de
	ldir
p_FillNum:
	.db 10
	ld	a,l
	pop	bc
	dec	bc
	pop	hl
	ld	(hl),a
	ld	d,h
	ld	e,l
	inc	de
	ldir
p_Copy:
	.db 5
	pop	de
	ex	(sp),hl
	pop	bc
	ldir
p_Copy2:
	.db 7
	ex	de,hl
	pop	hl
	ld	bc,768
	ldir
p_Copy1:
	.db 8
	ld	de,plotSScreen
	ld	bc,768
	ldir
p_CopyRev:
	.db 5
	pop	de
	ex	(sp),hl
	pop	bc
	lddr
p_Exchange:
	.db 12
	pop	de
	ex	(sp),hl
	pop	bc
	ld	a,(de)
	ldi
	dec	hl
	ld	(hl),a
	inc	hl
	jp	pe,$0000
	.db rp_Ans,2
p_Nib1:
	.db __Nib1End-$-1
	scf
	rr	h
	rr	l
	ld	a,(hl)
	jr	c,__Nib1Skip
	rrca
	rrca
	rrca
	rrca
__Nib1Skip:
	and	%00001111
	ld	l,a
	ld	h,0
	ret
__Nib1End:

p_Nib2:
	.db __Nib2End-$-1
	srl	h
	rr	l
	ld	a,(hl)
	jr	c,__Nib2Skip
	rrca
	rrca
	rrca
	rrca
__Nib2Skip:
	and	%00001111
	ld	l,a
	ld	h,0
	ret
__Nib2End:

p_NibSto:
	.db __NibStoEnd-$-1
	pop	bc
	pop	de
	push	bc
	scf
	rr	h
	rr	l
	jr	nc,__NibStoHigh
	rrd
	ld	a,e
	rld
	ret
__NibStoHigh:
	rld
	ld	a,e
	rrd
	ret
__NibStoEnd:

;Text
;-----------------------------------------------

;Homescreen Text
;-----------------------
p_DispStr:
	.db 3
	B_CALL(_PutS)
p_DispInt:
	.db 3
	B_CALL(_DispHL)
p_DispChar:
	.db 4
	ld	a,l
	B_CALL(_PutC)
p_DispTok:
	.db 6
	ld	e,(hl)
	inc	hl
	ld	d,(hl)
	B_CALL(_PutTokString)

;Homescreen App Text
;-----------------------
p_DispStrApp:
	.db __DispStrAppEnd-$-1
__DispStrAppLoop:
	ld	a,(hl)
	or	a
	ret	z
	inc	hl
	B_CALL(_PutC)
	jr	__DispStrAppLoop
__DispStrAppEnd:

;Graphscreen Text
;-----------------------
p_TextStr:
	.db 3
	B_CALL(_VPutS)
p_TextInt:
	.db __TextIntEnd-1-$
	B_CALL(_SetXXXXOP2)
	B_CALL(_Op2ToOP1)
	ld a,5
	B_CALL(_DispOP1A)
	ret
__TextIntEnd:

p_TextChar:
	.db 4
	ld	a,l
	B_CALL(_VPutMap)
p_TextTok:
	.db 10
	B_CALL(_Get_Tok_Strng)
	ld	b,a
	ld	hl,OP3
	B_CALL(_VPutSN)

;Graphscreen App Text
;-----------------------
p_TextStrApp:
	.db __TextStrAppEnd-$-1
__TextStrAppLoop:
	ld	a,(hl)
	or	a
	ret	z
	inc	hl
	B_CALL(_VPutMap)
	jr	nc,__TextStrAppLoop
	ret
__TextStrAppEnd:

;Cursor Position
;-----------------------
p_SetCurRow:
	.db 4
	ld	a,l
	ld	(CurRow),a
p_SetCurCol:
	.db 4
	ld	a,l
	ld	(CurCol),a
p_SetCurColRow:
	.db 3
	ld	(CurRow),hl
p_SetPenRow:
	.db 4
	ld	a,l
	ld	(PenRow),a
p_SetPenCol:
	.db 3
	ld	(PenCol),hl

;Text Flags
;-----------------------
p_TextSmall:
	.db 4
	res	2,(iy+50)
p_TextLarge:
	.db 4
	set	2,(iy+50)
p_TextNorm:
	.db 4
	res	3,(iy+5)
p_TextInv:
	.db 4
	set	3,(iy+5)
p_TextScrn:
	.db 4
	res	7,(iy+20)
p_TextBuf:
	.db 4
	set	7,(iy+20)
p_TextScroll:
	.db 4
	set	2,(iy+13)
p_TextNoScroll:
	.db 4
	res	2,(iy+13)
p_AlphaOff:
	.db 4
	res	3,(iy+$24)
p_AlphaOn:
	.db 4
	set	3,(iy+$24)

;Other Text Operations
;-----------------------
p_ClearScreen:
	.db 6
	B_CALL(_HomeUp)
	B_CALL(_ClrScrnFull)

p_NewLine:
	.db 3
	B_CALL(_NewLine)

p_Input:
	.db __InputEnd-$-1
	res	6,(iy+$1C)
	set	7,(iy+$09)
	xor	a
	ld	(ioPrompt),a
	B_CALL(_GetStringInput)
	B_CALL(_ZeroOP1)
	ld	a,$2D
	ld	(OP1+1),a
	rst	10h
	inc	de
	inc	de
	ex	de,hl
	ret
__InputEnd:

p_ToHex:
	.db __ToHexEnd-$-1
	ld	bc,$04E1
	ld	de,vx_SptBuff
__ToHexLoop:
	ld	a,c
__ToHexShift:
	add	hl,hl
	rla
	jr	c,__ToHexShift
	daa
	add	a,c
	adc	a,$3F
	ld	(de),a
	inc	e
	djnz	__ToHexLoop
	ex	de,hl
	ld	(hl),b
	ld	l,vx_SptBuff&$FF
	ret
__ToHexEnd:

p_ToHexFast:				;243 cycles, 34 bytes
	.db	__ToHexFast_End-$-1
	ex	de,hl
	ld	hl,vx_SptBuff+5
	ld	(hl),0
	ld	bc,$A040
	call	__ToHexFast_Byte-p_ToHexFast-1
x_ToHexFastEntry:
	ld	e,d
x_ToHexFastEntry2:
__ToHexFast_Byte:
	ld	a,e
	or	%11110000
	daa
	add	a,b
	adc	a,c
	dec	l
	ld	(hl),a
	ld	a,e
	rra
	rra
	rra
	rra
	or	%11110000
	daa
	add	a,b
	adc	a,c
	dec	l
	ld	(hl),a
	ret
__ToHexFast_End:

; Data Processing
;-----------------------

p_Length:
	.db __LengthEnd-$-1
	xor	a
	ld	b,h
	ld	d,h
	ld	e,l
	cpir
	scf
	sbc	hl,de
	ret
__LengthEnd:

p_InData:
	.db __InDataEnd-$-1
	pop	de
	pop	bc
	push	de
	ld	d,h
	ld	e,l
__InDataLoop:
	ld	a,(hl)
	or	a
	jr	z,__InDataDone
	inc	hl
	cp	c
	jr	nz,__InDataLoop
	.db	$C2			;jp nz
__InDataDone:
	ld	h,d
	ld	l,e
	sbc	hl,de
	ret
__InDataEnd:

p_InDataLen:
	.db __InDataLenEnd-$-1
	pop	af
	ex	(sp),hl
	pop	bc
	pop	de
	push	af
	ld	a,e
	add	hl,bc
	dec	hl
	cpdr
	ld	h,b
	ld	l,c
	ret	nz
	inc	hl
	ret
__InDataLenEnd:

p_NthStr:
	.db __NthStrEnd-$-1
	pop	bc
	pop	de
	push	bc
	ex	de,hl
__NthStrLoop:
	ld	a,d
	or	e
	ret	z
	xor	a
	cpir
	dec	de
	jr	__NthStrLoop
__NthStrEnd:

p_EquStr:
	.db __EquStrEnd-$-1
__EquStrLoop:
	ld	a,(de)
	cp	(hl)
	ret	nz
	inc	hl
	inc	de
	or	a
	jr	nz,__EquStrLoop
	ld	h,a
	ld	l,a
	ret
__EquStrEnd:

p_SortD:	;DE = data     L = size of data
	.db __SortDEnd-1-$
	ld	c,l
	ex	de,hl
__SortDLoop2:
	ld	b,c
	push	hl
	jr	__SortDJumpIn
__SortDLoop1:
	inc	hl
	cp	(hl)
	jr	c,__SortDSkip
__SortDJumpIn:
	ld	a,(hl)
	ld	d,h
	ld	e,l
__SortDSkip:
	djnz	__SortDLoop1
	ldi
	dec	hl
	ld	(hl),a
	pop	hl
	jp	pe,__SortDLoop2-p_SortD-1
	ret
__SortDEnd:

p_CheckSum:
	.db __CheckSumEnd-$-1
	ld	b,h
	ld	c,l
	pop	hl
	ex	(sp),hl
	xor	a
	ld	d,a
__CheckSumLoop:
	add	a,(hl)
	jr	nc,$+3
	inc	d
	cpi
	jp	pe,__CheckSumLoop-p_CheckSum-1
	ld	h,d
	ld	l,a
	ret
__CheckSumEnd:

;Buffer Operations
;-----------------------------------------------
p_ClearBuffer:
	.db 3
	B_CALL(_GrBufClr)

p_ClearBackBuffer:
	.db 6
	ld	hl,appBackUpScreen
	B_CALL(_BufClr)

p_ClearArbBuffer:
	.db 3
	B_CALL(_BufClr)

p_SaveToBuffer:
	.db 6
	ld	hl,plotSScreen
	B_CALL(_SaveDisp)

p_InvBuff:
	.db __InvBuffEnd-1-$
	ld	hl,plotSScreen
	ld	bc,3
__InvBuffLoop:
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	djnz	__InvBuffLoop
	dec	c
	jr	nz,__InvBuffLoop
	ret
__InvBuffEnd:

p_InvBuffFast:				;20118 cycles, 32 bytes
	.db __InvBuffFast_End-$-1
	ld	hl,plotSScreen
x_InvBuffFastEntry:
	ld	b,768/6
__InvBuffFast_Loop:
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	ld	a,(hl)
	cpl
	ld	(hl),a
	inc	hl
	djnz	__InvBuffFast_Loop
	ret
__InvBuffFast_End:

p_FrontToBack:
	.db 11
	ld	hl,plotSScreen
	ld	de,appBackUpScreen
	ld	bc,768
	ldir

p_BackToFront:
	.db 11
	ld	hl,appBackUpScreen
	ld	de,plotSScreen
	ld	bc,768
	ldir

;Buffer Shifting
;-----------------------------------------------
p_ShiftLeft:
	.db __ShiftLeftEnd-1-$
	ld	hl,plotSScreen+768
	xor	a
__ShiftLeftLoop:
	ld	b,12
__ShiftLeftShift:
	dec	hl
	rl	(hl)
	djnz	__ShiftLeftShift
	add	a,4
	jr	nz,__ShiftLeftLoop
	ret
__ShiftLeftEnd:

p_ShiftLeftFast:			;16982 cycles, 44 bytes
	.db __ShiftLeftFast_End-1-$
	ld	hl,plotSScreen+768
x_ShiftLeftFastEntry:
	ld	b,64
__ShiftLeftFast_Loop:
	dec	hl
	sla	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	dec	hl
	rl	(hl)
	djnz	__ShiftLeftFast_Loop
	ret
__ShiftLeftFast_End:

p_ShiftRight:
	.db __ShiftRightEnd-1-$
	ld	hl,plotSScreen
	xor	a
__ShiftRightLoop:
	ld	b,12
__ShiftRightShift:
	rr	(hl)
	inc	hl
	djnz	__ShiftRightShift
	add	a,4
	jr	nz,__ShiftRightLoop
	ret
__ShiftRightEnd:

p_ShiftRightFast:			;16982 cycles, 44 bytes
	.db __ShiftRightFast_End-1-$
	ld	hl,plotSScreen
x_ShiftRightFastEntry:
	ld	b,64
__ShiftRightFast_Loop:
	srl	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	rr	(hl)
	inc	hl
	djnz	__ShiftRightFast_Loop
	ret
__ShiftRightFast_End:

p_ShiftUp:
	.db __ShiftUpEnd-1-$
	ld	hl,plotSScreen+12
	ld	de,plotSScreen
x_ShiftUpEntry:
	ld	bc,768-12
	ldir
	ret
__ShiftUpEnd:

p_ShiftDown:
	.db __ShiftDownEnd-1-$
	ld	hl,plotSScreen+767-12
	ld	de,plotSScreen+767
x_ShiftDownEntry:
	ld	bc,768-12
	lddr
	ret
__ShiftDownEnd:

p_ShiftUSteal:
	.db 5
	ex	de,hl
	ld	hl,12
	add	hl,de

p_ShiftDSteal:
	.db 9
	inc	h
	inc	h
	inc	h
	dec	hl
	ex	de,hl
	ld	hl,-12
	add	hl,de

;Key Input
;-----------------------------------------------
p_GetKey:
	.db 6
	B_CALL(_GetCSC)
	ld	h,0
	ld	l,a

p_GetKeyPause:
	.db __GetKeyPauseEnd-1-$
	xor	a
	ld	(keyExtend),a
	B_CALL(_GetKeyRetOff)
	res	7,(iy+40)
	ld	hl,(keyExtend-1)
	ld	l,a
	ret
__GetKeyPauseEnd:

p_KbdScan:
	.db 3
	B_CALL(_kdbScan)

p_DKey:
	.db __DKeyEnd-1-$
	ld	a,d
	out	($01),a
	or	a
	push	af
	sbc	hl,hl
	pop	af
	in	a,($01)
	jr	z,__DKeyAll
	and	e
	ret	nz
__DKeyAll:
	inc	a
	ld	l,a
	ret
__DKeyEnd:

p_DKeyVar:
	.db __DKeyVarEnd-1-$
	ld	a,l
	ld	de,%0111111100000001
	rlc	d
	adc	a,%11110111
	jr	c,$-4
	rrc	e
	inc	a
	jr	nz,$-3
	jp	$3F00+sub_DirectKey
__DKeyVarEnd:

p_OnKey:
	.db 9
	in	a,(4)
	and	%00001000
	add	a,255
	sbc	hl,hl
	inc	hl

;System Settings
;-----------------------------------------------
p_DiagOn:
	.db 7
	B_CALL(_RunIndicOn)
	set	5,(iy+0)

p_DiagOff:
	.db 7
	B_CALL(_RunIndicOff)
	res	5,(iy+0)

p_SuspendHoriz:
	.db 9
	ld	a,(flags+sGrFlags)
	push	af
	or	$08
	call	0		;p_SuspendHoriz2 starting after pop af
	.db rp_Ans,2

p_SuspendHorz2:			;for a stupid TASM limitation
p_SuspendHoriz2:
	.db 17
	call	0		;whatever code immediately follows
	pop	af
	ld	(flags+sGrFlags),a
	B_CALL(_RESETWINTOP)
	B_CALL(_HomeUp)
	B_CALL(_ClrScrnFull)
	ret
	.db rp_Ans,16

p_SuspendMemDelays:
	.db 9
	in	a,($2E)
	push	af
	sub	$44
	sbc	a,a
	call	z,0
	.db rp_Ans,2

p_SuspendMemDelays2:
	.db 7
	call	0		;whatever code immediately follows
	pop	af
	out	($2E),a
	ret
	.db rp_Ans,6

p_FullSpeed:
	.db 8
	in	a,($02)
	rla
	sbc	a,a
	out	($20),a
	ld	l,a
	ld	h,a

p_NormalSpeed:
	.db 3
	xor	a
	out	($20),a

p_Contrast:
	.db 5
	ld	a,l
	or	%11000000
	out	($10),a

p_GetContrast:
	.db 8
	ld	a,(contrast)
	add	a,24
	ld	l,a
	ld	h,0

p_ZAddress:
	.db 7
	ld	a,l
	and	%00111111
	or	%01000000
	out	($10),a

;Link Port Stuff
;-----------------------------------------------
p_PortOut:
	.db 3
	ld	a,l
	out	($00),a
p_PortIn:
	.db 7
	in	a,($00)
	and	%00000011
	ld	l,a
	ld	h,0

p_FreqOut:
	.db __FreqOutEnd-1-$
	xor	a
__FreqOutLoop1:
	push	bc
	ld	e,a
__FreqOutLoop2:
	ld	a,h
	or	l
	jr	z,__FreqOutDone
	dec	hl
	dec	bc
	ld	a,b
	or	c
	jr	nz,__FreqOutLoop2
	ld	a,e
	xor	%00000011
	scf
__FreqOutDone:
	pop	bc
	out	($00),a
	ret	nc
	jr	__FreqOutLoop1
__FreqOutEnd:

p_GetByte:
	.db __GetByteEnd-$-1
	di
	ld	bc,$0803		;Bit counter in b, bit mask in c
	ld	hl,-1
	xor	a
	out	(0),a			;Make sure we are reset
	in	a,(0)
	and	c			;Check to see if sender is ready
	dec	a
	ret	nz			;If not, then go back
	inc	a
	out	(0),a			;Relay a confirmation
	ex	(sp),hl			;Wait at until confirmation is read (59 T-states minimum)
	ex	(sp),hl
	ld	a,(de)			;Bit counter in b and bitmask in c
	xor	a			;Store received byte in l
	nop
	inc	hl
	out	(0),a			;Reset the ports to receive data
__GetByteLoop:
	in	a,(0)			;Wait until first bit is sent Max loop wait (49 T-states max)
	and	c
	jr	z,__GetByteZero		;Go here if we get a zero
	cp	c
	jr	nz,__GetByteLoop
__GetByteOne:				;Go here if we get a one
	scf
__GetByteZero:
	rl	l			;Shift the bits left, zero is in the first bit
	ex	(sp),hl			;Wait for the sender to change (75 T-states min, 107 max)
	ex	(sp),hl
	djnz	__GetByteLoop		;Keep looping if we haven't got all the bits
	ret				;Otherwise, we're done.
__GetByteEnd:

p_SendByte:
	.db __SendByteEnd-$-1
	di
	ld	bc,$0803		;Bit counter in b, bit mask in c
	ld	a,%00000010
	out	(0),a			;Indicate we are ready to send
__SendByteTimeout:
	dec	hl
	ld	a,h
	or	l
	jr	z,__SendByteDone
	in	a,(0)			;Loop is 59 T-states maximum
	and	c
	jr	nz,__SendByteTimeout	;Keep looping till we get it
__SendByteLoop:
	inc	a
	out	(0),a			;This is the waiting state
	ex	(sp),hl			;Wait (115 T-states min)
	ex	(sp),hl
	ex	(sp),hl
	ex	(sp),hl
	xor	a
	ld	h,0
	ld	l,-1
	rl	e			;Check the first bit
	jr	c,__SendByteSkip
	ld	a,c			;Send a one
__SendByteSkip:				;Send a zero
	out	(0),a
	ex	(sp),hl			;Wait (59 T-states)
	ex	(sp),hl
	xor	a
	djnz	__SendByteLoop		;Loop if there are more bits to send
__SendByteDone:
	out	(0),a			;Reset the port
	ret				;We're done
__SendByteEnd:

;Multiplication, Division, and Modulo
;-----------------------------------------------
p_Mul:
	.db __MulEnd-1-$
	xor	a
	cp	h
	jr	z,$+3
	ex	de,hl
	ld	c,l
	ld	l,a
	add	a,h
	call	nz,__MulByte-p_Mul-1
x_MulEntry:
	ld	a,c
__MulByte:
	ld	b,8
__MulNext:
	add	hl,hl
	add	a,a
	jr	nc,__MulSkip
	add	hl,de
__MulSkip:
	djnz	__MulNext
	ret
__MulEnd:

p_MulFast:				;106 bytes
	.db __MulFastEnd-1-$
__MulFast_CheckShort:
	xor	a
	cp	h
	jr	nz,__MulFast_CheckShortDE
__MulFast_Short:
	or	l
	ret	z
__MulFast_ShortNZ:
	ld	l,0
__MulFast_IntFirstByte:
	add	a,a
	jr	c,__MulFast_Short_7
	add	a,a
	jr	c,__MulFast_Short_6
	add	a,a
	jr	c,__MulFast_Short_5
	add	a,a
	jr	c,__MulFast_Short_4
	add	a,a
	jr	c,__MulFast_Short_3
	add	a,a
	jr	c,__MulFast_Short_2
	add	a,a
	jr	c,__MulFast_Short_1
	ld	h,d
	ld	l,e
	ret
__MulFast_CheckShortDE:
	ex	de,hl
	cp	h
	jr	z,__MulFast_Short
__MulFast_CheckNegShort:
	inc	h
	jr	nz,__MulFast_ChkNegShortDE
__MulFast_NegShort:
	sub	l
	jr	z,__MulFast_Neg256
	call	__MulFast_ShortNZ-p_MulFast-1
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
	ret
__MulFast_Neg256:
	sub	e
	ld	h,a
	ret
__MulFast_ChkNegShortDE:
	dec	h
	ex	de,hl
	inc	h
	jr	z,__MulFast_NegShort
	dec	h
__MulFast_Int:
	ld	c,l
	ld	a,h
	call	__MulFast_IntFirstByte-p_MulFast-1
	ld	a,c
__MulFast_IntSecondByte:
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_7:
	add	hl,de
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_6:
	add	hl,de
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_5:
	add	hl,de
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_4:
	add	hl,de
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_3:
	add	hl,de
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_2:
	add	hl,de
	add	hl,hl
	add	a,a
	jr	nc,$+3
__MulFast_Short_1:
	add	hl,de
	add	hl,hl
	ret	p
	add	hl,de
	ret
__MulFastEnd:

p_MulFull:
	.db __MulFullEnd-1-$
	xor	a
	ld	c,h
	ld	h,a
	or	l
	ld	l,h
	call	nz,__MulFullByte-p_MulFull-1
x_MulFullEntry:
	ld	a,c
__MulFullByte:
	ld	b,8
__MulFullNext:
	rra
	jr	nc,__MulFullSkip
	add	hl,de
__MulFullSkip:
	rr	h
	rr	l
	djnz	__MulFullNext
	ret
__MulFullEnd:

p_88Mul:
	.db __88MulEnd-1-$
	push	hl
	call	$3F00+sub_MulFull
x_88MulEntry:
	rra
	ld	h,l
	ld	l,a
	ld	a,h
	pop	bc
	bit	7,b
	jr	z,$+4
	sub	e
	ld	h,a
	bit	7,d
	ret	z
	sub	c
	ld	h,a
	ret
__88MulEnd:

p_Recip:
	.db __RecipEnd-1-$
	xor	a
	bit	7,h
	push	af
	call	nz,__RecipNeg-p_Recip-3
	ex	de,hl
	ld	bc,16<<8+1
	ld	hl,2
	ld b,b \ .db 13 \ call $3F00+sub_Mod
x_RecipEntry:
	ld	h,a
	ld	l,c
	pop	af
	ret	z
__RecipNeg:
	ex	de,hl
	ld	h,a
	ld	l,a
	sbc	hl,de
	ret
__RecipEnd:

p_Div:
	.db __DivEnd-1-$
	ld	b,16
	ld	a,d
	or	a
	jr	z,__DivLoop8-2
	ld b,b \ .db 2 \ call $3F00+sub_Mod
x_DivEntry:
	ld	h,a
	ld	l,c
	ret
__DivLoop8:
	add	hl,hl
	rla
	jr	c,__DivOverflow
	cp	e
	jr	c,__DivSkip8
__DivOverflow:
	sub	e
	inc	l
__DivSkip8:
	djnz	__DivLoop8
	ret
__DivEnd:

p_Mod:
	.db __ModEnd-1-$
	ld	b,16
	ld	a,h
	ld	c,l
	ld	hl,0
x_ModEntry:
__ModLoop:
	scf
	rl	c
	rla
	adc	hl,hl
x_ModEntry2:
	sbc	hl,de
	jr	nc,__ModSkip
	add	hl,de
	dec	c
__ModSkip:
	djnz	__ModLoop
	ret
__ModEnd:

p_SDiv:
	.db __SDivEnd-1-$
	ld	a,h
	xor	d
	push	af
	xor	d
	jp	p,__SDivSkip1-p_SDiv-1
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
__SDivSkip1:
	bit	7,d
	jr	z,__SDivSkip2
	xor	a
	sub	e
	ld	e,a
	sbc	a,a
	sub	d
	ld	d,a
__SDivSkip2:
	call	$3F00+sub_Div
x_SDivEntry:
	pop	af
	ret	p
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
	ret
__SDivEnd:

p_88Div:
	.db __88DivEnd-$-1
	ld	a,h
	xor	d
	push	af
	xor	d
	jp	p,__88DivSkip1-p_88Div-1
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
__88DivSkip1:
	bit	7,d
	jr	z,__88DivSkip2
	xor	a
	sub	e
	ld	e,a
	sbc	a,a
	sub	d
	ld	d,a
__88DivSkip2:
	ld	bc,$1000
	ld	a,l
	ld	l,h
	ld	h,c
	ld b,b \ .db 7 \ call $3F00+sub_Mod
x_88DivEntry:
	ld	h,a
	ld	l,c
	pop	af
	ret	p
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
	ret
__88DivEnd:

;Pixel Routines
;-----------------------------------------------
p_Pix:
	.db __PixEnd-1-$		;Draws pixel (c,l)
	ld	de,plotSScreen
x_PixEntry:
	pop	af
	pop	bc
	push	af
	ld	a,c
x_PixEntry2:
	ld	b,0
	cp	96
	ld	a,b
	ret	nc
	sla	l
	ret	c
	sla	l
	ret	c

	ld	h,b
	ex	de,hl
	add	hl,de
	add	hl,de
	add	hl,de
	ld	a,c
	srl	c
	srl	c
	srl	c
	add	hl,bc
	and	%00000111
	ld	b,a
	ld	a,%10000000
	ret	z
___GetPixLoop:
	rrca
	djnz	___GetPixLoop
	ret
__PixEnd:

p_SetPix:
	.db 2
	or	(hl)
	ld	(hl),a
p_ResPix
	.db 3
	cpl
	and	(hl)
	ld	(hl),a
p_InvPix:
	.db 2
	xor	(hl)
	ld	(hl),a
p_GetPix:
	.db 6
	and	(hl)
	ld	h,b
	ld	l,b
	jr	z,$+3
	inc	l

;Basic Sprite Routines
;-----------------------------------------------
p_DrawSteal:
	.db 2
	pop	ix

p_GraySteal:
	.db 6
	push	hl
	pop	ix
	ld	hl,appBackUpScreen

p_DrawOr:
	.db __DrawOrEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer
x_DrawOrEntry:
	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af
	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawOrNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawOrClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawOrClipTop
__DrawOrNoClipTop:
	cp	b
	jr	nc,__DrawOrNoClipBot
	ld	b,a
__DrawOrNoClipBot:
	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawOrAligned
	ld	e,c
	ld	c,a
	ld	a,e
	cp	-7
	sbc	a,a
	ld	d,a
	and	e
	cp	96-7
	sbc	a,a
	ld	e,a
__DrawOrLoop:
	push	bc
	ld	b,c
	ld	c,(ix)
	xor	a
__DrawOrShift:
	srl	c
	rra
	djnz	__DrawOrShift
	and	e
	or	(hl)
	ld	(hl),a
	dec	hl
	ld	a,c
	and	d
	or	(hl)
	ld	(hl),a
	ld	c,13
	add	hl,bc
	inc	ix
	pop	bc
	djnz	__DrawOrLoop
	ret
__DrawOrAligned:
	ld	e,12
__DrawOrAlignedLoop:
	ld	a,(ix)
	or	(hl)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawOrAlignedLoop
	ret
__DrawOrEnd:

p_DrawOrFP:
	.db __DrawOrFPEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer

	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af

	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawOrFPNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawOrFPClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawOrFPClipTop
__DrawOrFPNoClipTop:
	cp	b
	jr	nc,__DrawOrFPNoClipBot
	ld	b,a
__DrawOrFPNoClipBot:

	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawOrFPAligned-4

#if 1
	push	hl
	cp	4
	jr	nc,$+3
	cpl
	add	a,4
	ld	e,a
	ld	a,a \ ld hl,__DrawOrFPShiftData-1-p_DrawOrFP-1
	add	hl,de
	ld	a,1
	jp	(hl)
__DrawOrFPShiftData:
	rrca
	rrca
	rrca
	nop
	nop
	nop
	jr	__DrawOrFPShiftDataEnd
	rlca
	rlca
	rlca
	rlca
	nop
	nop
	nop
__DrawOrFPShiftDataEnd:
	dec	a
	ld	e,a
	ld	a,c
	cp	h
	sbc	a,a
	and	e
	ld a,a \ ld (__DrawOrFPSMCMaskLeft-p_DrawOrFP-5),a
	ld	a,c
	add	a,7
	add	a,-96
	sbc	a,a
	or	e
	cpl
	ld a,a \ ld (__DrawOrFPSMCMaskRight-p_DrawOrFP-5),a
	ld a,a \ ld de,__DrawOrFPSMCShift-p_DrawOrFP-5
	ld	c,d
	ldi
	ldi
	ldi
	ldi
	ld	de,13
	pop	hl
#else
	push	hl
	ld	hl,__DrawOrFPSMCShift
	ld	e,4
	sub	e
	jr	z,__DrawOrFPRShift
	jr	nc,__DrawOrFPWriteShiftNops
	neg
__DrawOrFPWriteShiftNops:
	ld	(hl),d
	inc	hl
	dec	e
	dec	a
	jr	nz,__DrawOrFPWriteShiftNops
	jr	c,__DrawOrFPRShift
__DrawOrFPLShift:
	dec	a
__DrawOrFPWriteLShift:
	ld	(hl),$07
	inc	hl
	add	a,a
	dec	e
	jr	nz,__DrawOrFPWriteLShift
	jr	__DrawOrFPWriteShiftDone
__DrawOrFPRShift:
__DrawOrFPWriteRShift:
	ld	(hl),$1F
	inc	hl
	scf
	rra
	dec	e
	jr	nz,__DrawOrFPWriteRShift
__DrawOrFPWriteShiftDone:
	ld	e,a
	ld	a,c
	cp	89
	sbc	a,a
	and	e
	ld	(__DrawOrFPSMCMaskRight),a
	ld	a,c
	rla
	sbc	a,a
	or	e
	cpl
	ld	(__DrawOrFPSMCMaskLeft),a
	ld	e,13
	pop	hl
#endif

__DrawOrFPLoop:
	ld	a,(ix)
__DrawOrFPSMCShift:
	nop
	nop
	nop
	nop
	ld	c,a
__DrawOrFPSMCMaskRight .equ $+1
	and	0
	or	(hl)
	ld	(hl),a
	dec	hl
	ld	a,c
__DrawOrFPSMCMaskLeft .equ $+1
	and	0
	or	(hl)
	ld	(hl),a
	add	hl,de
	inc	ix
	djnz	__DrawOrFPLoop
	ret

__DrawOrFPAligned:
	ld	e,12
__DrawOrFPAlignedLoop:
	ld	a,(ix)
	or	(hl)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawOrFPAlignedLoop
	ret
__DrawOrFPEnd:

p_DrawXor:
	.db __DrawXorEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer
x_DrawXorEntry:
	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af
	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawXorNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawXorClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawXorClipTop
__DrawXorNoClipTop:
	cp	b
	jr	nc,__DrawXorNoClipBot
	ld	b,a
__DrawXorNoClipBot:
	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawXorAligned
	ld	e,c
	ld	c,a
	ld	a,e
	cp	-7
	sbc	a,a
	ld	d,a
	and	e
	cp	96-7
	sbc	a,a
	ld	e,a
__DrawXorLoop:
	push	bc
	ld	b,c
	ld	c,(ix)
	xor	a
__DrawXorShift:
	srl	c
	rra
	djnz	__DrawXorShift
	and	e
	xor	(hl)
	ld	(hl),a
	dec	hl
	ld	a,c
	and	d
	xor	(hl)
	ld	(hl),a
	ld	c,13
	add	hl,bc
	inc	ix
	pop	bc
	djnz	__DrawXorLoop
	ret
__DrawXorAligned:
	ld	e,12
__DrawXorAlignedLoop:
	ld	a,(ix)
	xor	(hl)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawXorAlignedLoop
	ret
__DrawXorEnd:

p_DrawXorFP:
	.db __DrawXorFPEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer

	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af

	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawXorFPNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawXorFPClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawXorFPClipTop
__DrawXorFPNoClipTop:
	cp	b
	jr	nc,__DrawXorFPNoClipBot
	ld	b,a
__DrawXorFPNoClipBot:

	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawXorFPAligned-4

#if 1
	push	hl
	cp	4
	jr	nc,$+3
	cpl
	add	a,4
	ld	e,a
	ld	a,a \ ld hl,__DrawXorFPShiftData-1-p_DrawXorFP-1
	add	hl,de
	ld	a,1
	jp	(hl)
__DrawXorFPShiftData:
	rrca
	rrca
	rrca
	nop
	nop
	nop
	jr	__DrawXorFPShiftDataEnd
	rlca
	rlca
	rlca
	rlca
	nop
	nop
	nop
__DrawXorFPShiftDataEnd:
	dec	a
	ld	e,a
	ld	a,c
	cp	h
	sbc	a,a
	and	e
	ld a,a \ ld (__DrawXorFPSMCMaskLeft-p_DrawXorFP-5),a
	ld	a,c
	add	a,7
	add	a,-96
	sbc	a,a
	or	e
	cpl
	ld a,a \ ld (__DrawXorFPSMCMaskRight-p_DrawXorFP-5),a
	ld a,a \ ld de,__DrawXorFPSMCShift-p_DrawXorFP-5
	ld	c,d
	ldi
	ldi
	ldi
	ldi
	ld	de,13
	pop	hl
#else
	push	hl
	ld	hl,__DrawXorFPSMCShift
	ld	e,4
	sub	e
	jr	z,__DrawXorFPRShift
	jr	nc,__DrawXorFPWriteShiftNops
	neg
__DrawXorFPWriteShiftNops:
	ld	(hl),d
	inc	hl
	dec	e
	dec	a
	jr	nz,__DrawXorFPWriteShiftNops
	jr	c,__DrawXorFPRShift
__DrawXorFPLShift:
	dec	a
__DrawXorFPWriteLShift:
	ld	(hl),$07
	inc	hl
	add	a,a
	dec	e
	jr	nz,__DrawXorFPWriteLShift
	jr	__DrawXorFPWriteShiftDone
__DrawXorFPRShift:
__DrawXorFPWriteRShift:
	ld	(hl),$1F
	inc	hl
	scf
	rra
	dec	e
	jr	nz,__DrawXorFPWriteRShift
__DrawXorFPWriteShiftDone:
	ld	e,a
	ld	a,c
	cp	89
	sbc	a,a
	and	e
	ld	(__DrawXorFPSMCMaskRight),a
	ld	a,c
	rla
	sbc	a,a
	or	e
	cpl
	ld	(__DrawXorFPSMCMaskLeft),a
	ld	e,13
	pop	hl
#endif

__DrawXorFPLoop:
	ld	a,(ix)
__DrawXorFPSMCShift:
	nop
	nop
	nop
	nop
	ld	c,a
__DrawXorFPSMCMaskRight .equ $+1
	and	0
	xor	(hl)
	ld	(hl),a
	dec	hl
	ld	a,c
__DrawXorFPSMCMaskLeft .equ $+1
	and	0
	xor	(hl)
	ld	(hl),a
	add	hl,de
	inc	ix
	djnz	__DrawXorFPLoop
	ret

__DrawXorFPAligned:
	ld	e,12
__DrawXorFPAlignedLoop:
	ld	a,(ix)
	xor	(hl)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawXorFPAlignedLoop
	ret
__DrawXorFPEnd:

p_DrawOff:
	.db __DrawOffEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer
x_DrawOffEntry:
	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af
	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawOffNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawOffClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawOffClipTop
__DrawOffNoClipTop:
	cp	b
	jr	nc,__DrawOffNoClipBot
	ld	b,a
__DrawOffNoClipBot:
	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawOffAligned
	ld	e,c
	ld	c,a
	ld	a,e
	cp	-7
	jr	nc,__DrawOffLoop
	inc	d
	cp	96-7
	jr	nc,__DrawOffLoop
	inc	d
__DrawOffLoop:
	push	bc
	ld	b,c
	ld	c,(ix+0)
	xor	a
	ld	e,$FF
__DrawOffShift:
	srl	c
	rr	e
	rra
	djnz	__DrawOffShift
	dec	d
	jr	z,__DrawOffSkipRight
	ld	b,a
	or	(hl)
	and	e
	ld	(hl),a
	ld	a,b
__DrawOffSkipRight:
	dec	hl
	inc	d
	jr	z,__DrawOffSkipLeft
	and	(hl)
	or	c
	ld	(hl),a
__DrawOffSkipLeft:
	ld	bc,13
	add	hl,bc
	inc	ix
	pop	bc
	djnz	__DrawOffLoop
	ret
__DrawOffAligned:
	ld	e,12
__DrawOffAlignedLoop:
	ld	a,(ix)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawOffAlignedLoop
	ret
__DrawOffEnd:

p_DrawAnd:
	.db __DrawAndEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer
x_DrawAndEntry:
	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af
	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawAndNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawAndClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawAndClipTop
__DrawAndNoClipTop:
	cp	b
	jr	nc,__DrawAndNoClipBot
	ld	b,a
__DrawAndNoClipBot:
	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawAndAligned
	ld	e,c
	ld	c,a
	ld	a,e
	rla
	sbc	a,a
	ld	d,a
	xor	e
	add	a,-(96-7)
	sbc	a,a
	ld	e,a
__DrawAndLoop:
	push	bc
	ld	b,c
	ld	c,(ix)
	scf
	sbc	a,a
__DrawAndShift:
	rr	c
	rra
	djnz	__DrawAndShift
	or	e
	and	(hl)
	ld	(hl),a
	dec	hl
	ld	a,c
	or	d
	and	(hl)
	ld	(hl),a
	ld	c,13
	add	hl,bc
	inc	ix
	pop	bc
	djnz	__DrawAndLoop
	ret
__DrawAndAligned:
	ld	e,12
__DrawAndAlignedLoop:
	ld	a,(ix)
	and	(hl)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawAndAlignedLoop
	ret
__DrawAndEnd:

p_DrawAndFP:
	.db __DrawAndFPEnd-1-$
	push	hl
	pop	ix			;Input ix = Sprite
	ld	hl,plotSScreen		;Input hl = Buffer

	pop	af
	pop	de			;Input e = Sprite Y Position
	pop	bc			;Input c = Sprite X Position
	push	af

	ld	b,7
	ld	a,63
	sub	e
	jr	nc,__DrawAndFPNoClipTop
	ld	a,e
	add	a,b
	ret	nc
__DrawAndFPClipTop:
;	xor	b
;	ld	e,a
;	add	ix,de
;	ld	e,d
;	xor	b
	inc	ix
	inc	e
	jr	nz,__DrawAndFPClipTop
__DrawAndFPNoClipTop:
	cp	b
	jr	nc,__DrawAndFPNoClipBot
	ld	b,a
__DrawAndFPNoClipBot:

	inc	b
	ld	a,c
	add	a,7
	cp	96+7
	ret	nc
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de
	ld	a,c
	and	7
	jr	z,__DrawAndFPAligned-4

#if 1
	push	hl
	cp	4
	jr	nc,$+3
	cpl
	add	a,4
	ld	e,a
	ld	a,a \ ld hl,__DrawAndFPShiftData-1-p_DrawAndFP-1
	add	hl,de
	ld	a,1
	jp	(hl)
__DrawAndFPShiftData:
	rrca
	rrca
	rrca
	nop
	nop
	nop
	jr	__DrawAndFPShiftDataEnd
	rlca
	rlca
	rlca
	rlca
	nop
	nop
	nop
__DrawAndFPShiftDataEnd:
	dec	a
	ld	e,a
	ld	a,c
	cp	h
	sbc	a,a
	and	e
	cpl
	ld a,a \ ld (__DrawAndFPSMCMaskLeft-p_DrawAndFP-5),a
	ld	a,c
	add	a,7
	add	a,-96
	sbc	a,a
	or	e
	ld a,a \ ld (__DrawAndFPSMCMaskRight-p_DrawAndFP-5),a
	ld a,a \ ld de,__DrawAndFPSMCShift-p_DrawAndFP-5
	ld	c,d
	ldi
	ldi
	ldi
	ldi
	ld	de,13
	pop	hl
#else				;still needs to be converted to and
	push	hl
	ld	hl,__DrawAndFPSMCShift
	ld	e,4
	sub	e
	jr	z,__DrawAndFPRShift
	jr	nc,__DrawAndFPWriteShiftNops
	neg
__DrawAndFPWriteShiftNops:
	ld	(hl),d
	inc	hl
	dec	e
	dec	a
	jr	nz,__DrawAndFPWriteShiftNops
	jr	c,__DrawAndFPRShift
__DrawAndFPLShift:
	dec	a
__DrawAndFPWriteLShift:
	ld	(hl),$07
	inc	hl
	add	a,a
	dec	e
	jr	nz,__DrawAndFPWriteLShift
	jr	__DrawAndFPWriteShiftDone
__DrawAndFPRShift:
__DrawAndFPWriteRShift:
	ld	(hl),$1F
	inc	hl
	scf
	rra
	dec	e
	jr	nz,__DrawAndFPWriteRShift
__DrawAndFPWriteShiftDone:
	ld	e,a
	ld	a,c
	cp	89
	sbc	a,a
	and	e
	ld	(__DrawAndFPSMCMaskRight),a
	ld	a,c
	rla
	sbc	a,a
	or	e
	cpl
	ld	(__DrawAndFPSMCMaskLeft),a
	ld	e,13
	pop	hl
#endif

__DrawAndFPLoop:
	ld	a,(ix)
__DrawAndFPSMCShift:
	nop
	nop
	nop
	nop
	ld	c,a
__DrawAndFPSMCMaskRight .equ $+1
	or	0
	and	(hl)
	ld	(hl),a
	dec	hl
	ld	a,c
__DrawAndFPSMCMaskLeft .equ $+1
	or	0
	and	(hl)
	ld	(hl),a
	add	hl,de
	inc	ix
	djnz	__DrawAndFPLoop
	ret

__DrawAndFPAligned:
	ld	e,12
__DrawAndFPAlignedLoop:
	ld	a,(ix)
	and	(hl)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawAndFPAlignedLoop
	ret
__DrawAndFPEnd:

#if 0
p_EzSprite:
	.db 6
	pop	bc
	pop	de
	ld	d,c
	B_CALL(_DisplayImage)
#endif

p_GetSprite:
	.db __GetSpriteEnd-1-$		;Gets sprite at (c,l) into 8 bytes at IX
	ld	de,plotSScreen
	ld	ix,vx_SptBuff
x_GetSpriteEntry:
	pop	af
	pop	bc
	push	af
	push	ix
	ld	a,l
	add	a,a
	add	a,l
	ld	l,a
	add	hl,hl
	add	hl,hl
	add	hl,de
	ld	a,c
	sra	c
	sra	c
	sra	c
	add	hl,bc
	and	%00000111
	ld	b,8
	jr	nz,___GetSpriteUnaligned
	ld	de,12
___GetSpriteAligned:
	ld	a,(hl)
	ld	(ix),a
	add	hl,de
	inc	ix
	djnz	___GetSpriteAligned
	pop	hl
	ret
___GetSpriteUnaligned:
	ld	d,(hl)
	inc	hl
	ld	e,(hl)
	ex	de,hl
	ld	c,a
___GetSpriteShift:
	add	hl,hl
	dec	c
	jr	nz,___GetSpriteShift
	ld	(ix),h
	ld	hl,11
	add	hl,de
	inc	ix
	djnz	___GetSpriteUnaligned
	pop	hl
	ret
__GetSpriteEnd:

p_BmpSteal:
	.db 4
	ld	a,l
	pop	ix
	pop	hl

p_DrawBmp:
	.db __DrawBmpEnd-1-$		;****** RE-ORDER STACK ******
	ld	ix,plotSScreen		;HL = Sprite [X,Y,data]
	xor	a
x_DrawBmpEntry:
	ex	(sp),hl
	pop	de
	pop	bc
	ex	(sp),hl
	push	af
	ex	de,hl
	ld	d,e			;****** BEGIN CLIPPING ******
	ld	a,(hl)			;A = width
	dec	a			;A = width - 1
	rrca				;A = (bytes - 1)*4 + junk
	rrca				;A = (bytes - 1)*2 + junk
	rrca				;A = (bytes - 1) + junk
	and	%00011111		;A = bytes - 1
	inc	a			;A = bytes
	ld	e,a
	ld	a,c
	ld	c,e			;C = bytes
	ld	b,a			;B = Y
	sub	64
	ld	e,a			;E = Y' = Y - 64
	inc	hl
	ld	a,(hl)			;A = height
	jr	c,__DrawBmpClipBot
	dec	a
	add	a,b
	jr	c,__DrawBmpNoRet	;Return if hidden on top
	pop	af
	ret
__DrawBmpNoRet:
	xor	a			;A = 0
	sub	b			;A = -Y
	ld	b,a			;B = -Y
	add	a,e			;A = -64
	ld	e,a			;E = -64
	push	de
	ld	d,0
	ld	e,c			;DE = bytes
	ld	a,(hl)			;A = height
__DrawBmpTopLoop:
	add	hl,de
	dec	a
	djnz	__DrawBmpTopLoop	;HL = HL - width*Y
	pop	de
__DrawBmpClipBot:
	add	a,e			;A = Y' + newheight
	jr	nc,__DrawBmpClipDone
	xor	a
__DrawBmpClipDone:
	sub	e			;A = min(Y + height , 64) - max(Y , 0)
	jr	nz,__DrawBmpGoodSize
	sub	e
__DrawBmpGoodSize:
	ld	b,a			;B = plot_height
	push	bc			;****** BEGIN BUFFER CALCULATIONS ******
	inc	hl			;HL = Start of sprite data
	push	hl
	ld	a,e
	add	a,64			;A = Y
	ld	b,0			;BC = Y
	ld	c,a
	add	a,a			;A = Y*2
	ld	h,b
	ld	l,a			;HL = Y*2
	add	hl,bc			;HL = Y*3
	add	hl,hl			;HL = Y*6
	add	hl,hl			;HL = Y*12
	ld	a,d
	cp	96
	jr	nc,__DrawBmpSkipBuf
	and	%11111000
	rrca				;A = X/2
	rrca				;A = X/4
	rrca				;A = X/8
	ld	c,a			;C = X/8
	add	hl,bc			;HL = Y*12 + X/8
__DrawBmpSkipBuf:
	ld	b,h
	ld	c,l
 	add	ix,bc			;IX = buff + Y*12 + X/8
 	pop	hl			;HL = Start of sprite data
	pop	bc
	pop	af
__DrawBmpMainLoop:			;****** BEGIN DRAWING SPRITE ******
	push	bc
	push	ix
	push	de
	push	af
	ld	a,d
	cp	96
	jr	c,__DrawBmpOnRight
__DrawBmpLeftLoop:
	inc	c
	dec	c
	jr	z,__DrawBmpSkipMain
	dec	c
	add	a,8
	jr	c,__DrawBmpOnLeft
	inc	hl
	jr	__DrawBmpLeftLoop
__DrawBmpOnLeft:			;A = X + 8
	inc	c
	dec	c
	ld	d,(hl)
	inc	hl
	ld	e,c			;E = 0 if z
	jr	z,__DrawBmpSt
	ld	e,(hl)
	jr	__DrawBmpSt
__DrawBmpOnRight:
	ld	a,d			;A = X
	ld	d,0
__DrawBmpColLoop:
	ld	e,(hl)			;DE = to be shifted
__DrawBmpSt:				;****** BEGIN SHIFTING SPRITE ******
	push	af
	and	%00000111
	ld	b,a
	jr	z,__DrawBmpStSkip
	ld	a,d
__DrawBmpStLoop:
	rra
	rr	e
	djnz	__DrawBmpStLoop
__DrawBmpStSkip:
	ld	a,e
	pop	de			;D = X
	ld	e,c
	pop	bc
	ld	c,e			;C = bytes
	djnz	__DrawBmpOr
	xor	(ix+0)
	jr	__DrawBmpWrite
__DrawBmpOr:
	or	(ix+0)
__DrawBmpWrite:
	inc	b
	push	bc
	ld	(ix+0),a		;Draw onto buffer
	inc	ix			;Next col of buffer
__DrawBmpColWall:
	inc	c
	dec	c
	jr	z,__DrawBmpSkipMain
	dec	c
	ld	a,d
	jr	nz,__DrawBmpColLeft
	cp	88
	ld	d,(hl)
	inc	hl
	jr	nc,__DrawBmpSkipMain
	ld	e,c
	jr	__DrawBmpSt
__DrawBmpColLeft:
	add	a,8
	inc	hl
	jr	c,__DrawBmpColWall
	ld	d,a
	cp	96
	jr	nc,__DrawBmpColWall
	dec	hl
	ld	d,(hl)
	inc	hl			;Next col of sprite
	jr	__DrawBmpColLoop
__DrawBmpSkipMain:
	pop	af
	pop	de
	pop	ix
	ld	bc,12
	add	ix,bc
	pop	bc
	djnz	__DrawBmpMainLoop
	ret
__DrawBmpEnd:


;Advanced Math
;-----------------------------------------------
p_Sqrt:
	.db __SqrtEnd-1-$
	ld	a,l
	ld	l,h
	ld	de,$0040
	ld	h,d
	ld	b,8
	or	a
__SqrtLoop:
	sbc	hl,de
	jr	nc,__SqrtSkip
	add	hl,de
__SqrtSkip:
	ccf
	rl	d
	rla
	adc	hl,hl
	rla
	adc	hl,hl
	djnz	__SqrtLoop
	ld	h,b
	ld	l,d
	ret
__SqrtEnd:

p_Sqrt88:
	.db __Sqrt88End-1-$
	ld	b,12
	ld	a,h
	ld	c,l
	ld	de,0
	ld	h,d
	ld	l,e
__Sqrt88Loop:
	sub	$40
	sbc	hl,de
	jr	nc,__Sqrt88Skip
	add	a,$40
	adc	hl,de
__Sqrt88Skip:
	ccf
	rl	e
	rl	d
	sla	c
	rla
	adc	hl,hl
	sla	c
	rla
	adc 	hl,hl
	djnz	__Sqrt88Loop
	ex	de,hl
	ret
__Sqrt88End:

p_Sin:
	.db __SinEnd-1-$
	ld	a,l
	add	a,64
	ld	l,a
x_SinEntry:
	ld	a,l
	ld	c,a
	add	a,a
	ld	d,a
	cpl
	ld	e,a
	xor	a
	ld	b,8
__SinLoop:
	rra
	rrc	e
	jr	nc,__SinSkip
	add	a,d
__SinSkip:
	djnz	__SinLoop
	ld	l,a
	ld	h,b
	or	c
	ret	p
	xor	a
	sub	l
	ret	z
	ld	l,a
	dec	h
	ret
__SinEnd:

p_Log:
	.db 10
	ld	de,16
	scf
__LogLoop:
	adc	hl,hl
	dec	de
	jr	nc,__LogLoop
	ex	de,hl

p_Exp:
	.db 10
	ld	b,l
	inc	b
	ld	hl,0
	scf
__ExpLoop:
	adc	hl,hl
	djnz	__ExpLoop

p_ArcTan:
	.db __ArcTanEnd-1-$
	ex	de,hl		;de = y
	pop	hl
	ex	(sp),hl		;hl = x
	push	hl
	ld	a,h		;Get pairity
	xor	d
	jp	m,__ArcTanSS-p_ArcTan-1
	add	hl,de		; |
	jr	__ArcTanDS	; |
__ArcTanSS:			; |hl = x +- y
	sbc	hl,de		; |
__ArcTanDS:			;/
	ex	de,hl		;de = x +- y
	ld	b,6		;\
__ArcTan64:			; |
	add	hl,hl		; |hl = 64y
	djnz	__ArcTan64	;/
	call	$3F00+sub_SDiv	;hl = 64y/(x +- y)
x_ArcTanEntry2:
	pop	af		;\
	rla			; |Right side, fine
	ret	nc		;/
	sbc	a,a		;\
	sub	h		; |Reverse sign extend
	ld	h,a		;/
	ld	a,l		;\
	add	a,128		; |Add or sub 128
	ld	l,a		;/
	ret
__ArcTanEnd:

;VAT Manipulation
;-----------------------------------------------
p_GetCalc:
	.db __GetCalcEnd-1-$
	rst	20h
	B_CALL(_ChkFindSym)
	ld	hl,0
	ret	c
	dec	b
	ret	p
	ex	de,hl
	and	%00011111
	ret	z		;Ret if real
	cp	CplxObj
	ret	z		;Ret if complex
	inc	hl
	inc	hl
	ret			;Otherwise add 2
__GetCalcEnd:

p_NewVar:
	.db __NewVarEnd-1-$
	B_CALL(_EnoughMem)
	pop	hl
	ex	(sp),hl
	jr	c,__NewVarFail
	push	de
	push	hl
	rst	20h
	B_CALL(_ChkFindSym)
	jr	c,__NewVarSkip
	B_CALL(_DelVarArc)
__NewVarSkip:
	pop	hl
	ld	a,(hl)
	rst	20h
	pop	hl
	push	af
	B_CALL(_CreateVar)
	pop	af
	ex	de,hl
	and	%00011111
	ret	z
	cp	CplxObj
	ret	z
	inc	hl
	inc	hl
	ret
__NewVarFail:
	ld	hl,0
	ret
__NewVarEnd:

p_Unarchive:
	.db __UnarchiveEnd-1-$
	rst	20h
	B_CALL(_ChkFindSym)
	ld	hl,0
	ret	c
	inc	b
	dec	b
	ret	z
	B_CALL(_Arc_Unarc)
	ld	hl,1
	ret
__UnarchiveEnd:

p_Archive:
	.db __ArchiveEnd-1-$
	rst	20h
	B_CALL(_ChkFindSym)
	ld	hl,0
	ret	c
	inc	b
	dec	b
	ret	nz
	B_CALL(_Arc_Unarc)
	ld	hl,1
	ret
__ArchiveEnd:

p_DelVar:
	.db 9
	rst	20h
	B_CALL(_ChkFindSym)
	jr	c,$+5
	B_CALL(_DelVarArc)

p_GetArc:
	.db __GetArcEnd-1-$
	push	de
	rst	20h
	B_CALL(_ChkFindSym)
	jr	c,__GetArcFail
	inc	b
	djnz	__GetArcRom
__GetArcRam:
	ld	h,b
	ld	l,b
__GetArcChkFloat:
	and	%00011111
	jr	z,__GetArcDone
	cp	CplxObj
	jr	z,__GetArcDone
	jr	__GetArcSkipSize
__GetArcRom:
	B_CALL(_IsFixedName)
	ld	hl,$C00C
	jr	nz,__GetArcChkFloat
	ld	l,9
__GetArcRomNamed:
	add	hl,de
	bit	6,h
	jr	z,$+3
	inc	b
	set	6,h
	B_CALL(_LoadDEIndPaged)
	ld	d,$C0
__GetArcSkipSize:
	inc	de
	inc	de
__GetArcDone:
	add	hl,de
	ex	de,hl
	pop	hl
	ld	(hl),e
	inc	hl
	ld	(hl),d
	inc	hl
	ld	(hl),b
	ret
__GetArcFail:
	ld	hl,0
	pop	de
	ret
__GetArcEnd:

p_ReadArc:
	.db __ReadArcEnd-1-$
	or	a
	jr	z,__ReadArcRam
	ld	c,a
	in	a,(6)
	ld	b,a
	ld	a,h
	set	6,h
	res	7,h
	rlca
	rlca
	and	%00000011
	add	a,c
	out	(6),a
	ld	c,(hl)
	inc	hl
	bit	7,h
	jr	z,__ReadArcNoBound
	ld	h,%01000000
	inc	a
	out	(6),a
__ReadArcNoBound:
	ld	h,(hl)
	ld	l,c
	ld	a,b
	out	(6),a
	ret
__ReadArcRam:
	ld	a,(hl)
	inc	hl
	ld	h,(hl)
	ld	l,a
	ret
__ReadArcEnd:

p_ReadArcApp:
	.db __ReadArcAppEnd-1-$
	or	a
	jr	z,__ReadArcAppRam-2
	ld	c,a
	xor	a
	ld b,b \ .db 12 \ call $3F00+sub_Safety	;Hijack safety to skip speed stuff.
	push	af
	in	a,(7)
	ld	b,a
	ld	a,h
	res	6,h
	set	7,h
	rlca
	rlca
	and	%00000011
	add	a,c
	out	(7),a
	ld	c,(hl)
	inc	hl
	bit	6,h
	jr	z,__ReadArcAppNoBound
	ld	h,%10000000
	inc	a
	out	(7),a
__ReadArcAppNoBound:
	ld	h,(hl)
	ld	l,c
	ld	a,b
	out	(7),a
	pop	af
	ret	c
	ei
	ret
__ReadArcAppRam:
	ld	a,(hl)
	inc	hl
	ld	h,(hl)
	ld	l,a
	ret
__ReadArcAppEnd:

p_CopyArc:
	.db __CopyArcEnd-1-$
	ex	(sp),hl
	pop	bc
	pop	de
	ex	(sp),hl
	or	a
	jr	z,__CopyArcRam
	push	bc
	ld	b,a
	ld	a,h
	rlca
	rlca
	and	%00000011
	add	a,b
	set	6,h
	res	7,h
	pop	bc
	B_CALL(_FlashToRAM)
	ret
__CopyArcRam:
	ldir
	ret
__CopyArcEnd:

;Screen Display Commands
;-----------------------------------------------
p_FastCopy:
	.db __FastCopyEnd-1-$
	ld	hl,plotSScreen
	ld	a,$80
	out	($10),a
	call	$3F00+sub_Safety
x_FastCopyEntry:
	push	af
	ld	a,$1F
__FastCopyAgain:
	inc	a
	out	($10),a		;many cc into, 72cc loop
	cp	$2B
	ld	bc,64<<9+$11
	push	hl
	inc	de		;waste
__FastCopyLoop:
	push	af		;semi waste
	ld	de,11
	outi			;71cc into, 71cc loop
	add	hl,de
	pop	af		;semi waste
	djnz	__FastCopyLoop
	pop	hl
	inc	hl
	jr	c,__FastCopyAgain
__FastCopyRestore:
	pop	af
	out	($20),a
	ret	c
	ei
	ret
__FastCopyEnd:

p_DrawAndClr:
	.db __DrawAndClrEnd-1-$
	ld	hl,plotSScreen
	ld	c,-12
	ld	a,$80
	out	($10),a
	call	$3F00+sub_Safety
x_DrawAndClrEntry:
	push	af
__DrawAndClrAgain:
	push	hl
	ld	a,c
	add	a,$2C
	out	($10),a		;many cc into, 73cc loop
	ld	de,4
	ld	b,64
__DrawAndClrLoop:
	ld	a,(hl)
	ld	(hl),d
	add	hl,de		;semi waste
	add	hl,de		;semi waste
	add	hl,de		;semi waste
	out	($11),a		;75cc into, 71cc loop
	djnz	__DrawAndClrLoop
	pop	hl
	inc	hl
	inc	c
	jr	nz,__DrawAndClrAgain
__DrawAndClrRestore:
	pop	af
	out	($20),a
	ret	c
	ei
	ret
__DrawAndClrEnd:

p_DrawRcl:
	.db __DrawRclEnd-1-$
	ld	hl,plotSScreen
	ld	ix,appBackupScreen
	ld	a,$80
	out	($10),a
	call	$3F00+sub_Safety
x_DrawRclEntry:
	push	af
	ld	a,$20
	ld	de,12
__DrawRclNext:
	out	($10),a		;many cc into, 129cc loop
	inc	a
	cp	$2C
	push	af
	push	hl
	push	ix
	ld	b,32
__DrawRclLoop:
	ld	a,(hl)
	out	($11),a		;73cc into, 79cc loop
	ld	a,(ix)
	ld	(hl),a
	add	hl,de
	ld	c,(ix+12)
	ld	a,(hl)
	out	($11),a		;74cc into
	ld	(hl),c
	add	ix,de
	add	ix,de
	add	hl,de
	djnz	__DrawRclLoop
	pop	ix
	pop	hl
	inc	ix
	inc	hl
	pop	af
	jr	nz,__DrawRclNext
__DrawRclRestore:
	pop	af
	out	($20),a
	ret	c
	ei
	ret
__DrawRclEnd:

p_DispGS:
	.db	__DispGSEnd-1-$
	ld	de,plotSScreen
	ld	hl,appBackUpScreen
	ex	de,hl
	call	$3F00+sub_Safety
x_DispGSEntry:
	push	af
	ld	a,$07
	out	($10),a		;many cc into
	ld	bc,flags+asm_Flag2
	ld	a,(bc)
	rra
	sbc	a,a
	xor	%01010101
	ld	(bc),a
	ld	c,a
	ld	a,$80
__DispGSNext:
	push	af
	out	($10),a		;72cc into, 71cc loop
	ex	(sp),hl		;waste
	ex	(sp),hl		;waste
	rrc	c
	ld	b,12
	ld	a,$20
	out	($10),a		;71cc into
	pop	af		;semi waste
	inc	a
	push	af		;semi waste
__DispGSLoop:
	ld	a,(de)
	and	c
	or	(hl)
	inc	de
	inc	hl
	ret	c		;waste
	out	($11),a		;71cc into, 71cc loop
	ret	c		;waste
	ld	a,(hl)		;waste
	djnz	__DispGSLoop
	pop	af
	cp	$C0
	jr	nz,__DispGSNext
__DispGSDone:
	pop	af
	out	($20),a
	ld	a,$05
	out	($10),a		;65+18cc into
	ret	c
	ei
	ret
__DispGSEnd:

p_DispGSClr:
	.db	__DispGSClrEnd-1-$
	ld	de,plotSScreen
	ld	hl,appBackUpScreen
	ex	de,hl
	call	$3F00+sub_Safety
x_DispGSClrEntry:
	push	af
	ld	a,$07
	out	($10),a		;many cc into
	ld	bc,$9D55
	ld	a,(bc)
	rra
	sbc	a,a
	xor	c
	ld	(bc),a
	ld	b,a
	ld	a,$80
	nop			;waste
__DispGSClrNext:
	push	af		;semi waste
	out	($10),a		;73cc into, 71cc loop
	ex	(sp),hl		;waste
	ex	(sp),hl		;waste
	ld	c,24
	rrc	b
	ld	a,$20
	out	($10),a		;71cc into
	pop	af		;semi waste
	inc	a
	cp	$C0
	push	af
__DispGSClrLoop:
	ld	a,(de)
	and	b
	or	(hl)
	ld	(hl),0
	out	($11),a		;71cc into, 71cc loop
	ldi
	dec	c
	jr	nz,__DispGSClrLoop
	pop	af
	jr	nz,__DispGSClrNext
__DispGSClrDone:
	pop	af
	out	($20),a
	ld	a,$05
	out	($10),a		;65+18cc into
	ret	c
	ei
	ret
__DispGSClrEnd:

p_Disp4Lvl:
	.db __Disp4LvlEnd-1-$
	ld	de,plotSScreen
	ld	hl,appBackUpScreen
	call	$3F00+sub_Safety
x_Disp4LvlEntry:
	push	af
	ld	a,$07
	out	($10),a		;many cc into
	ld	a,%10110110
	cp	(iy+asm_flag2)
	jr	c,__Disp4LvlSkip
	ld	a,%11011011
	jr	nz,__Disp4LvlSkip
	rra
__Disp4LvlSkip:
	ld	(flags+asm_flag2),a
	ld	c,a
	ld	a,$80
__Disp4LvlNext:
	ld	b,12
	out	($10),a		;76+cc into, 72cc loop
	inc	a
	rr	c
	push	af
	push	af		;waste
	ex	(sp),hl		;waste
	ld	a,$20
	out	($10),a		;71cc into
	ex	(sp),hl		;waste
	pop	af		;waste
__Disp4LvlLoop:
	ld	a,(de)
	xor	(hl)
	and	c
	xor	(hl)
	inc	bc		;waste
	out	($11),a		;71cc into, 71cc loop
	dec	c		;waste
	inc	de
	inc	hl
	djnz	__Disp4LvlLoop
	pop	af
	bit	6,a
	jr	z,__Disp4LvlNext
__Disp4LvlDone:
	pop	af
	out	($20),a
	ld	a,$05
	out	($10),a		;70+18cc into
	ret	c
	ei
	ret
__Disp4LvlEnd:

p_Disp4Clr:
	.db	__Disp4ClrEnd-1-$
	ld	de,plotSScreen
	ld	hl,appBackUpScreen
	call	$3F00+sub_Safety
	push	af
	ld	a,$07
	out	($10),a		;many cc into
	ld	a,%10110110
	cp	(iy+asm_flag2)
	jr	c,__Disp4ClrSkip
	ld	a,%11011011
	jr	nz,__Disp4ClrSkip
	rra
__Disp4ClrSkip:
	ld	(flags+asm_flag2),a
	ld	b,a
	ld	a,$80
__Disp4ClrNext:
	out	($10),a		;73+cc into, 71cc loop
	inc	a
	rr	b
	push	af
	ld	c,18
	dec	c		;waste
	ex	(sp),hl		;waste
	ld	a,$20
	out	($10),a		;71cc into
	ex	(sp),hl		;waste
	inc	bc		;waste
	ret	z		;waste
__Disp4ClrLoop:
	ld	a,(de)
	xor	(hl)
	and	b
	xor	(hl)
	ret	c		;waste
	out	($11),a		;56cc into, 71cc loop
	ld	(hl),0
	ldi
	ld	a,(de)
	xor	(hl)
	and	b
	xor	(hl)
	ld	(hl),0
	out	($11),a		;72cc into
	ldi
	dec	c
	jp	nz,__Disp4ClrLoop-p_Disp4Clr-1
	pop	af
	bit	6,a
	jr	z,__Disp4ClrNext
__Disp4ClrDone:
	pop	af
	out	($20),a
	ld	a,$05
	out	($10),a		;76+18cc into
	ret	c
	ei
	ret
__Disp4ClrEnd:

;Geometry Drawing
;-----------------------------------------------
#if 0
p_HLineFull:
	.db __HLineFullEnd-$-1
	ld	de,plotSScreen
	ex	de,hl
x_HLineFullEntry:

;; e=y, hl=buff
;; Calculate y*4; if the 8-bit value overflows, abort
	sla	e
	ret	c
	sla	e
	ret	c

;; e=y*4, hl=buff
;; Add y*12 to the buffer pointer
	ld	d,0
	add	hl,de
	add	hl,de
	add	hl,de

;; y no longer needed
;; hl=y*12+buff
;; Draw the line
	ld	bc,12*256+$FF
	ld	(hl),c
	inc	hl
	djnz	$-2

	ret
__HLineFullEnd:
#endif

p_HVLineSteal:
	.db 4
	ld	l,-128
	push	hl
	dec	l

p_HLine:
	.db __HLineEnd-$-1
	ld	de,plotSScreen

;; de=buff, l=x2, (sp)=ret, (sp+2)=x1, (sp+4)=y
;; Call the shared horizontal line routine, which performs clipping, performs 
;;   buffer pointer adjustment, and calculates the first mask; if the line is 
;;   fully offscreen, it aborts the drawing entirely
	call	$3F00+sub_HLineShr

x_HLineEntry:
;; a=first mask, b=0, c=x2, d=0, e=x1, hl=y*12+(x1/8)+buff
;; Prepare the first byte and calculate the negative remaining width after the 
;;   first byte; if positive, jump to the masking code for the last byte
	or	(hl)
	ld	d,a
	ld	a,e
	or	%00000111
	sub	c
	jr	nc,__HLineRight

;; a=-width remaining, b=0, c=x2, d=byte, e=x1, hl=y*12+(x1/8)+buff
;; Draw bytes until there is no width remaining
__HLineMidLoop:
	ld	(hl),d
	inc	hl
	ld	d,$FF
	add	a,8
	jr	nc,__HLineMidLoop

;; a=width remaining-1%8+1, b=0, c=x2, d=byte, e=x1, hl=y*12+(x2/8)+buff
;; Calculate the mask for the last byte
__HLineRight:
	ld	b,a
	inc	b
	ld	a,$7F
__HLineRightLoop:
	rlca
	djnz	__HLineRightLoop
	inc	a

;; a=mask, b=0, c=x2, d=byte, e=x1, hl=y*12+(x2/8)+buff
;; Draw the last byte
	and	d
	or	(hl)
	ld	(hl),a

	ret
__HLineEnd:

p_WHLine:
	.db __WHLineEnd-$-1
	ld	de,plotSScreen

;; de=buff, l=x2, (sp)=ret, (sp+2)=x1, (sp+4)=y
;; Call the shared horizontal line routine, which performs clipping, performs 
;;   buffer pointer adjustment, and calculates the first mask; if the line is 
;;   fully offscreen, it aborts the drawing entirely
	call	$3F00+sub_HLineShr

x_WHLineEntry:
;; a=first mask, b=0, c=x2, d=0, e=x1, hl=y*12+(x1/8)+buff
;; Prepare the first byte and calculate the negative remaining width after the 
;;   first byte; if positive, jump to the masking code for the last byte
	cpl
	and	(hl)
	ld	d,a
	ld	a,e
	or	%00000111
	sub	c
	jr	nc,__WHLineRight

;; a=-width remaining, b=0, c=x2, d=byte, e=x1, hl=y*12+(x1/8)+buff
;; Draw bytes until there is no width remaining
__WHLineMidLoop:
	ld	(hl),d
	inc	hl
	ld	d,$00
	add	a,8
	jr	nc,__WHLineMidLoop

;; a=width remaining-1%8+1, b=0, c=x2, d=byte, e=x1, hl=y*12+(x2/8)+buff
;; Calculate the mask for the last byte
__WHLineRight:
	ld	b,a
	inc	b
	ld	a,$80
__WHLineRightLoop:
	rlca
	djnz	__WHLineRightLoop
	dec	a

;; a=mask, b=0, c=x2, d=byte, e=x1, hl=y*12+(x2/8)+buff
;; Draw the last byte
	or	d
	and	(hl)
	ld	(hl),a

	ret
__WHLineEnd:

p_IHLine:
	.db __IHLineEnd-$-1
	ld	de,plotSScreen

;; de=buff, l=x2, (sp)=ret, (sp+2)=x1, (sp+4)=y
;; Call the shared horizontal line routine, which performs clipping, performs 
;;   buffer pointer adjustment, and calculates the first mask; if the line is 
;;   fully offscreen, it aborts the drawing entirely
	call	$3F00+sub_HLineShr

x_IHLineEntry:
;; a=first mask, b=0, c=x2, d=0, e=x1, hl=y*12+(x1/8)+buff
;; Calculate the negative remaining width after the first byte; if positive, 
;;   jump to the masking code for the last byte
	ld	d,a
	ld	a,e
	or	%00000111
	sub	c
	jr	nc,__IHLineRight

;; a=-width remaining, b=0, c=x2, d=mask, e=x1, hl=y*12+(x1/8)+buff
;; Draw bytes until there is no width remaining
__IHLineMidLoop:
	ld	e,a
	ld	a,(hl)
	xor	d
	ld	(hl),a
	inc	hl
	ld	a,e
	ld	d,$FF
	add	a,8
	jr	nc,__IHLineMidLoop

;; a=width remaining-1%8+1, b=0, c=x2, d=mask, e=previous a, hl=y*12+(x2/8)+buff
;; Calculate the mask for the last byte
__IHLineRight:
	ld	b,a
	inc	b
	ld	a,$7F
__IHLineRightLoop:
	rlca
	djnz	__IHLineRightLoop
	inc	a

;; a=mask, b=0, c=x2, d=byte, e=x1, hl=y*12+(x2/8)+buff
;; Draw the last byte
	and	d
	xor	(hl)
	ld	(hl),a

	ret
__IHLineEnd:

p_HLineShr:
	.db __HLineShrEnd-$-1

;; de=buff, l=x2, (sp)=ret_cont, (sp+2)=ret_abort, (sp+4)=x1, (sp+6)=y
;; Rearrange stuff
	ld	a,l
	pop	ix
	pop	hl
	pop	bc
	ex	(sp),hl

;; a=x2, c=x1, de=buff, l=y, ix=ret_cont, (sp)=ret_abort
;; Check if x2 is offscreen left; if so, note and fix it
	ld	h,0
	ld	b,a
	rla
	jr	nc,$+3
	ld	b,h

;; carry=x2 offscreen, b=left-fixed x2, c=x1, de=buff, h=0, l=y, ix=ret_cont
;; Check if x1 is offscreen left; if so, abort if x2 was too, then fix it
	bit	7,c
	jr	z,$+4
	ret	c
	ld	c,h

;; b=left-fixed x2, c=left-fixed x1, de=buff, h=0, l=y, ix=ret_cont
;; Locate the greater and lesser of x1 and x2
	ld	a,c
	cp	b
	jr	nc,$+4
	ld	c,b
	ld	b,a

;; x1 is now guaranteed to be <=x2
;; b=left-fixed x1, c=left-fixed x2, de=buff, h=0, l=y, ix=ret_cont
;; Check if x1 is offscreen right; if so, abort
	ld	a,95
	cp	b
	ret	c

;; a=95, b=fixed x1, c=left-fixed x2, de=buff, h=0, l=y, ix=ret_cont
;; Check if x2 is offscreen right; if so, fix it
	cp	c
	jr	nc,$+3
	ld	c,a

;; X Clipping complete; x1 and x2 guaranteed to be onscreen
;; a=95, b=x1, c=x2, de=buff, h=0, l=y, ix=ret_cont
;; Calculate y*4; if the 8-bit value overflows, abort
	add	hl,hl
	add	hl,hl
	and	h
	ret	nz

;; a=0, b=x1, c=x2, de=buff, h=0, l=y*4, ix=ret_cont
;; Calculate x1/8 and add it and y*12 to the buffer pointer
	ld	a,b
	ex	de,hl
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de

;; y no longer needed
;; a=x1/8, b=x1, c=x2, d=0, e=x1/8, hl=y*12+(x1/8)+buff, ix=ret_cont
;; Calculate the mask for the first byte
	ld	e,b
	ld	a,b
	and	%00000111
	jr	z,__HLineShrLeft8
	ld	b,a
	ld	a,$01
__HLineShrLeftLoop:
	rrca
	djnz	__HLineShrLeftLoop
__HLineShrLeft8:
	dec	a

;; a=first mask, b=0, c=x2, d=0, e=x1, hl=y*12+(x1/8)+buff, ix=ret_cont
;; Return to the specific drawing routine
	jp	(ix)

__HLineShrEnd:

#if 0
p_VLineFull:
	.db __VLineFullEnd-$-1
	ld	de,plotSScreen
	ex	de,hl
x_VLineFullEntry:

;; e=x, hl=buff
;; Calulate the mask
	ld	a,e
	and	%00000111
	ld	b,a
	inc	b
	ld	c,$01
__VLineFullMaskLoop:
	rrc	c
	djnz	__VLineFullMaskLoop

;; a=e%8, b=0, c=mask, e=x, hl=buff
;; Calculate x/8 and add it to the buffer pointer
	xor	e
	rrca
	rrca
	rrca
	ld	e,a
	ld	d,b
	add	hl,de

;; a=x/8, b=0, c=mask, d=0, e=x/8, hl=x/8+buff
;; If x if offscreen, abort
	ld	e,12
	cp	e
	ret	nc

;; x no longer needed
;; a=x/8, b=0, c=mask, de=12, hl=x/8+buff
;; Draw the line
	ld	b,64
__VLineFullLoop:
	ld	a,(hl)
	or	c
	ld	(hl),a
	add	hl,de
	djnz	__VLineFullLoop

	ret
__VLineFullEnd:
#endif

p_VLine:
	.db __VLineEnd-$-1
	ld	de,plotSScreen

;; de=buff, l=y2, (sp)=ret, (sp+2)=y1, (sp+4)=x
;; Call the shared horizontal line routine, which performs clipping, performs 
;;   buffer pointer adjustment, and calculates the first mask; if the line is 
;;   fully offscreen, it aborts the drawing entirely
	call	$3F00+sub_VLineShr

x_VLineEntry:
;; a=0, b=height, c=mask, de=12, hl=y1*12+(x/8)+buff
;; Draw the line
__VLineLoop:
	ld	a,(hl)
	or	c
	ld	(hl),a
	add	hl,de
	djnz	__VLineLoop

	ret
__VLineEnd:

p_WVLine:
	.db __WVLineEnd-$-1
	ld	de,plotSScreen

;; de=buff, l=y2, (sp)=ret, (sp+2)=y1, (sp+4)=x
;; Call the shared horizontal line routine, which performs clipping, performs 
;;   buffer pointer adjustment, and calculates the first mask; if the line is 
;;   fully offscreen, it aborts the drawing entirely
	call	$3F00+sub_VLineShr

x_WVLineEntry:
;; a=0, b=height, c=mask, de=12, hl=y1*12+(x/8)+buff
;; Invert the mask
	ld	a,c
	cpl
	ld	c,a

;; a=0, b=height, c=inverted mask, de=12, hl=y1*12+(x/8)+buff
;; Draw the line
__WVLineLoop:
	ld	a,(hl)
	and	c
	ld	(hl),a
	add	hl,de
	djnz	__WVLineLoop

	ret
__WVLineEnd:

p_IVLine:
	.db __IVLineEnd-$-1
	ld	de,plotSScreen

;; de=buff, l=y2, (sp)=ret, (sp+2)=y1, (sp+4)=x
;; Call the shared horizontal line routine, which performs clipping, performs 
;;   buffer pointer adjustment, and calculates the first mask; if the line is 
;;   fully offscreen, it aborts the drawing entirely
	call	$3F00+sub_VLineShr

x_IVLineEntry:
;; a=0, b=height, c=mask, de=12, hl=y1*12+(x/8)+buff
;; Draw the line
__IVLineLoop:
	ld	a,(hl)
	xor	c
	ld	(hl),a
	add	hl,de
	djnz	__IVLineLoop

	ret
__IVLineEnd:

p_VLineShr:
	.db __VLineShrEnd-$-1

;; de=buff, l=y2, (sp)=ret_cont, (sp+2)=ret_abort (sp+4)=y1, (sp+6)=x
;; Rearrange stuff
	ld	a,l
	pop	ix
	pop	hl
	pop	bc
	ex	(sp),hl

;; a=y2, c=y1, de=buff, l=x, ix=ret_cont, (sp)=ret_abort
;; Check if y1 is offscreen top while calculating y1*2; if so, abort if y2 is 
;;   too, then fix it
	ld	h,0
	sla	c
	jr	nc,$+5
	or	a
	ret	m
	ld	c,h

;; a=y2, c=top-fixed y1*2, de=buff, h=0, l=x, ix=ret_cont
;; Check if y2 is offscreen top while calculating y2*2; if so, fix it
	add	a,a
	jr	nc,$+3
	ld	a,h

;; a=top-fixed y2*2, c=top-fixed y1*2, de=buff, h=0, l=x, ix=ret_cont
;; Check that y2>=y1; if not, swap y1 and y2
	cp	c
	jr	nc,$+5
	ld	b,c
	ld	c,a
	ld	a,b

;; y1 is now guaranteed to be <=y2
;; a=top-fixed y2*2, c=top-fixed y1*2, de=buff, h=0, l=x, ix=ret_cont
;; Check if y1 is offscreen bottom while calculating y1*4; if so, abort
	sla	c
	ret	c

;; a=top-fixed y2*2, c=fixed y1*4, de=buff, h=0, l=x, ix=ret_cont
;; Check if y2 is offscreen bottom while calculating y2*4; if so, fix it
	add	a,a
	jr	nc,$+4
	ld	a,63*4

;; Y Clipping complete; y1 and y2 guaranteed to be onscreen
;; a=y2*4, c=y1*4, de=buff, h=0, l=x, ix=ret_cont
;; Calculate the height of the line
	sub	c
	rra
	rra
	inc	a
	ld	b,a

;; y2 no longer needed
;; a=height, b=height, c=y1*4, de=buff, h=0, l=x, ix=ret_cont
;; Calculate x1/8 and add it and y*12 to the buffer pointer
	ex	de,hl
	ld	a,e
	ld	e,c
	ld	c,a
	add	hl,de
	rra
	add	hl,de
	rra
	add	hl,de
	rra
	ld	e,a
	add	hl,de


;; y1 no longer needed
;; a=x/8, b=height, c=x, d=0, e=x/8, hl=y1*12+(x/8)+buff, ix=ret_cont
;; Check if x is offscreen; if so, abort
	ld	e,12
	cp	e
	ret	nc

;; a=x/8, b=height, c=x, de=12, hl=y1*12+(x/8)+buff, ix=ret_cont
;; Calculate the mask
	ld	a,c
	or	%11111000
	ld	c,$80
__VLineShrMaskLoop:
	rlc	c
	inc	a
	jr	nz,__VLineShrMaskLoop


;; a=0, b=height, c=mask, de=12, hl=y1*12+(x/8)+buff
;; Return to the specific drawing routine
	jp	(ix)

__VLineShrEnd:

p_Line:
	.db __LineEnd-$-1
	ld	ix,plotSScreen
	call	$3F00+sub_LineShr
x_LineEntry:
	ret	nc
	jr	nz,__LineHLoop		; Line is rather horizontal than vertical
__LineVLoop:
	push	af
	ld	a,(ix+0)
	or	c			; Writing pixel to current position
	ld	(ix+0),a
	pop	af
	add	ix,de
	sub	h			; Handling gradient
	jr	nc,__LineVNext
	add	a,l
	rrc	c			; Rotating mask
	jr	nc,__LineVNext		; Handling byte boundary
	inc	ix
__LineVNext:
	djnz	__LineVLoop
	ret
__LineHLoop:
	push	af			; Saving A
	ld	a,(ix+0)
	or	c			; Writing pixel to current position
	ld	(ix+0),a
	pop	af			; Recalling A
	rrc	c			; Rotating mask
	jr	nc,__LineHSkip		; Handling byte boundary
	inc	ix
__LineHSkip:
	sub	l			; Handling gradient
	jr	nc,__LineHNext
	add	a,h
	add	ix,de
__LineHNext:
	djnz	__LineHLoop
	ret
__LineEnd:

p_WLine:
	.db __WLineEnd-$-1
	ld	ix,plotSScreen
	call	$3F00+sub_LineShr
x_WLineEntry:
	ret	nc
	push	af
	ld	a,c
	cpl
	ld	c,a
	pop	af
	jr	nz,__WLineHLoop		; Line is rather horizontal than vertical
__WLineVLoop:
	push	af
	ld	a,(ix+0)
	and	c			; Writing pixel to current position
	ld	(ix+0),a
	pop	af
	add	ix,de
	sub	h			; Handling gradient
	jr	nc,__WLineVNext
	add	a,l
	rrc	c			; Rotating mask
	jr	c,__WLineVNext		; Handling byte boundary
	inc	ix
__WLineVNext:
	djnz	__WLineVLoop
	ret
__WLineHLoop:
	push	af			; Saving A
	ld	a,(ix+0)
	and	c			; Writing pixel to current position
	ld	(ix+0),a
	pop	af			; Recalling A
	rrc	c			; Rotating mask
	jr	c,__WLineHSkip		; Handling byte boundary
	inc	ix
__WLineHSkip:
	sub	l			; Handling gradient
	jr	nc,__WLineHNext
	add	a,h
	add	ix,de
__WLineHNext:
	djnz	__WLineHLoop
	ret
__WLineEnd:

p_ILine:
	.db __ILineEnd-$-1
	ld	ix,plotSScreen
	call	$3F00+sub_LineShr
x_ILineEntry:
	ret	nc
	jr	nz,__ILineHLoop		; Line is rather horizontal than vertical
__ILineVLoop:
	push	af
	ld	a,(ix+0)
	xor	c			; Writing pixel to current position
	ld	(ix+0),a
	pop	af
	add	ix,de
	sub	h			; Handling gradient
	jr	nc,__ILineVNext
	add	a,l
	rrc	c			; Rotating mask
	jr	nc,__ILineVNext		; Handling byte boundary
	inc	ix
__ILineVNext:
	djnz	__ILineVLoop
	ret
__ILineHLoop:
	push	af			; Saving A
	ld	a,(ix+0)
	xor	c			; Writing pixel to current position
	ld	(ix+0),a
	pop	af			; Recalling A
	rrc	c			; Rotating mask
	jr	nc,__ILineHSkip		; Handling byte boundary
	inc	ix
__ILineHSkip:
	sub	l			; Handling gradient
	jr	nc,__ILineHNext
	add	a,h
	add	ix,de
__ILineHNext:
	djnz	__ILineHLoop
	ret
__ILineEnd:

p_LineShr:
	.db __LineShrEnd-$-1
;; l=y2, ix=buff, (sp)=ret, (sp+2)=ret_2, (sp+4)=x2, (sp+6)=y1, (sp+8)=x1
	ld	a,l
	pop	bc
	pop	hl
	pop	de
	ex	(sp),hl
	ld	d,l
	pop	hl
	ex	(sp),hl
	push	bc

;; a=y2, d=y1, e=x2, l=x1, (sp)=ret, (sp+2)=ret_2
	cp	64
	ret	nc
	ld	h,a
	ld	a,d
	cp	64
	ret	nc

	ld	a,l
	cp	96
	ret	nc
	ld	a,e
	cp	96
	ret	nc

	sub	l
	jr	nc,__LineShrSkipRev
	ex	de,hl
	neg

;; a=dx, d=y1, e=x2, h=y2, l=x1
__LineShrSkipRev:
	push	af			; Saving DX (it will be popped into HL below)
	ld	a,l			; IX+=L/8+D*12 (actually D*4+D*4+D*4)
	rra
	rra
	rra
	and	%00011111
	ld	c,a
	ld	b,0
	add	ix,bc
	ld	a,d
	add	a,a
	add	a,a
	ld	c,a
	add	ix,bc
	add	ix,bc
	add	ix,bc
	ld	a,l			; Calculating the starting pixel mask
	and	%00000111
	inc	a
	ld	b,a
	ld	a,%00000001
__LineShrMaskLoop:
	rrca
	djnz	__LineShrMaskLoop
	ld	c,a
	ld	a,h			; Calculating delta Y and negating the Y increment if necessary
	sub	d			; This is the last instruction for which we need the original data
	ld	de,12
	jr	nc,__LineShrSkipNeg
	ld	de,-12
	neg
__LineShrSkipNeg:
	pop	hl			; Recalling DX
	ld	l,a			; H=DX, L=DY
	cp	h
	jr	nc,__LineVert		; Line is rather vertical than horizontal
	ld	a,h
__LineVert:
	ld	b,a			; Pixel counter
	inc	b
	cp	l
	scf				; Setting up gradient counter
	ccf
	rra
	scf
	ret				; c=1, z=vertical major
__LineShrEnd:

p_Rect:
	.db __RectEnd-$-1
	ld	de,plotSScreen
	call	$3F00+sub_RectShr
x_RectEntry:
__RectShift:			;Input:  b = Left shift
	add	a,8		;Input:  a = negative right shift
	sub	b		;Output: a = mask
	ld	c,$FF
__RectShift1:
	srl	c
	dec	a
	jr	nz,__RectShift1
	ld	a,c
	cpl
	inc	b
	rlca
__RectShift2:
	rrca
	djnz	__RectShift2
	ld	c,a
__RectLoop1:			;(e,d) = (width,height)
	push	hl		;    c = bitmask
	ld	b,d
	push	de
	ld	de,12
__RectLoop2:
	ld	a,c
	or	(hl)
	ld	(hl),a
	add	hl,de
	djnz	__RectLoop2
	pop	de
	pop	hl
	inc	hl
	ld	a,e
	or	a
	ret	z
	sub	8
	ld	e,b
	jr	c,__RectShift
	ld	e,a
	ld	c,$FF
	jr	__RectLoop1
__RectEnd:

p_WRect:
	.db __WRectEnd-$-1
	ld	de,plotSScreen
	call	$3F00+sub_RectShr
x_WRectEntry:
__WRectShift:			;Input:  b = Left shift
	add	a,8		;Input:  a = negative right shift
	sub	b		;Output: a = mask
	ld	c,$FF
__WRectShift1:
	srl	c
	dec	a
	jr	nz,__WRectShift1
	ld	a,c
	inc	b
	rlca
__WRectShift2:
	rrca
	djnz	__WRectShift2
__WRectLoop1:			;(e,d) = (width,height)
	push	hl		;    a = bitmask
	ld	b,d
	ld	c,a
	push	de
	ld	de,12
__WRectLoop2:
	ld	a,c
	and	(hl)
	ld	(hl),a
	add	hl,de
	djnz	__WRectLoop2
	pop	de
	pop	hl
	inc	hl
	ld	a,e
	or	a
	ret	z
	sub	8
	ld	e,b
	jr	c,__WRectShift
	ld	e,a
	xor	a
	jr	__WRectLoop1
__WRectEnd:

p_IRect:
	.db __IRectEnd-$-1
	ld	de,plotSScreen
	call	$3F00+sub_RectShr
x_IRectEntry:
__IRectShift:			;Input:  b = Left shift
	add	a,8		;Input:  a = negative right shift
	sub	b		;Output: a = mask
	ld	c,$FF
__IRectShift1:
	srl	c
	dec	a
	jr	nz,__IRectShift1
	ld	a,c
	cpl
	inc	b
	rlca
__IRectShift2:
	rrca
	djnz	__IRectShift2
	ld	c,a
__IRectLoop1:			;(e,d) = (width,height)
	push	hl		;    c = bitmask
	ld	b,d
	push	de
	ld	de,12
__IRectLoop2:
	ld	a,c
	xor	(hl)
	ld	(hl),a
	add	hl,de
	djnz	__IRectLoop2
	pop	de
	pop	hl
	inc	hl
	ld	a,e
	or	a
	ret	z
	sub	8
	ld	e,b
	jr	c,__IRectShift
	ld	e,a
	ld	c,$FF
	jr	__IRectLoop1
__IRectEnd:

p_RectShr:
	.db __RectShrEnd-$-1
;; de=buff, l=height, (sp)=ret_cont, (sp+2)=ret_abort, (sp+4)=width, (sp+6)=y, (sp+8)=x
	ld	a,l
	pop	ix
	pop	hl
	pop	bc
	ex	(sp),hl
	ld	b,l
	pop	hl
	ex	(sp),hl

;; a=height, b=y, c=width, de=buff, l=x, ix=ret_cont, (sp)=ret_abort
	bit	7,b		;Clip top
	jr	z,__RectShrNoClipTop
	add	a,b
	ret	nc
	ld	b,0
__RectShrNoClipTop:
	ld	h,a

;; a=height, b=y, c=width, de=buff, h=height, l=x, ix=ret_cont, (sp)=ret_abort
	or	a		;Check for height being zero
	ret	z

	ld	a,c		;Clip left
	bit	7,l
	jr	z,__RectShrNoClipLeft
	add	a,l
	ret	nc
	ld	l,0
	ld	c,a
__RectShrNoClipLeft:

	or	a		;Check for width being zero
	ret	z

	ld	a,63		;Clip bottom
	sub	b
	ret	c
	inc	a
	cp	h
	jr	nc,$+3
	ld	h,a

	ld	a,95		;Clip right
	sub	l
	ret	c
	inc	a
	cp	c
	jr	nc,$+3
	ld	c,a

	ex	de,hl
	push	de
	xor	a
	ld	d,a
	ld	a,e
	rra
	sla	b
	rra
	sla	b
	rra
	ld	e,a
	add	hl,de
	ld	e,b
	add	hl,de
	add	hl,de
	add	hl,de
	pop	de

;; a=x/8, b=y*4, c=width, d=height, e=x, hl=y*12+(x/8)+buff
	ld	a,e
	and	%00000111
	ld	b,a
	add	a,c
	sub	8
	ld	e,0
	jr	c,__RectShrSkip
	ld	e,a
	xor	a
__RectShrSkip:

;; a=negative right shift, b=left shift, d=height, e=width, hl=y*12+(x/8)+buff
	jp	(ix)
__RectShrEnd:

p_Circle:
	.db __CircleEnd-$-1
	ld	ix,plotSScreen
	ld	e,l
	pop	hl
	pop	bc
	ex	(sp),hl
	ld	b,l
	xor	a
	ld	l,a
	sub	e		;(CX,CY) = (b,c)
	ld	d,a		;(er,x,y) = (d,e,l)

__CircleLoop:
	ld	a,%11011101

__CircleDraw8:
	add	a,a
	push	af
	jr	nc,__CircleSwap
	xor	a
	sub	e
	ld	e,a
__CircleSwap:
	push	hl
	push	de
	push	bc

	ld	a,l
	add	a,c
	ld	l,a
	ld	a,e
	add	a,b
	ld	c,a
	push	ix
	pop	de
	ld b,b \ .db 7 \ call $3F00+sub_Pix
	or	(hl)
	ld	(hl),a

	pop	bc
	pop	hl
	pop	de
	pop	af
	jr	nz,__CircleDraw8+2

	ld	a,d
	add	a,l
	inc	l
	add	a,l
	jp	m,__CircleSkip-p_Circle-3
	dec	e
	sub	e
	sub	e
__CircleSkip:
	ld	d,a
	ld	a,e
	cp	l
	jr	nc,__CircleLoop+2
	ret
__CircleEnd:

p_WCircle:
	.db __WCircleEnd-$-1
	ld	ix,plotSScreen
	ld	e,l
	pop	hl
	pop	bc
	ex	(sp),hl
	ld	b,l
	xor	a
	ld	l,a
	sub	e		;(CX,CY) = (b,c)
	ld	d,a		;(er,x,y) = (d,e,l)

__WCircleLoop:
	ld	a,%11011101

__WCircleDraw8:
	add	a,a
	push	af
	jr	nc,__WCircleSwap
	xor	a
	sub	e
	ld	e,a
__WCircleSwap:
	push	hl
	push	de
	push	bc

	ld	a,l
	add	a,c
	ld	l,a
	ld	a,e
	add	a,b
	ld	c,a
	push	ix
	pop	de
	ld b,b \ .db 7 \ call $3F00+sub_Pix
	cpl
	and	(hl)
	ld	(hl),a

	pop	bc
	pop	hl
	pop	de
	pop	af
	jr	nz,__WCircleDraw8+2

	ld	a,d
	add	a,l
	inc	l
	add	a,l
	jp	m,__WCircleSkip-p_WCircle-3
	dec	e
	sub	e
	sub	e
__WCircleSkip:
	ld	d,a
	ld	a,e
	cp	l
	jr	nc,__WCircleLoop+2
	ret
__WCircleEnd:

p_ICircle:
	.db __ICircleEnd-$-1
	ld	ix,plotSScreen
	ld	e,l
	pop	hl
	pop	bc
	ex	(sp),hl
	ld	b,l
	xor	a
	ld	l,a
	sub	e		;(CX,CY) = (b,c)
	ld	d,a		;(er,x,y) = (d,e,l)

	ld	a,%01010000

__ICircleLoop:
	add	a,a
	push	af
	jr	nc,__ICircleSwap
	xor	a
	sub	l
	ld	l,a
__ICircleSwap:
	push	hl
	push	de
	push	bc

	ld	a,l
	add	a,c
	ld	l,a
	ld	a,e
	add	a,b
	ld	c,a
	push	ix
	pop	de
	ld b,b \ .db 7 \ call $3F00+sub_Pix
	xor	(hl)
	ld	(hl),a

	pop	bc
	pop	hl
	pop	de
	pop	af
	jr	nz,__ICircleLoop+2

	ld	a,d
	add	a,l
	inc	l
	add	a,l
	jp	m,__ICircleSkip-p_ICircle-3
	dec	e
	sub	e
	sub	e
__ICircleSkip:
	ld	d,a
	ld	a,l
	cp	e
	ld	a,%11011101
	jr	c,__ICircleLoop+2
	ret	nz
	ld	a,%11110000
	jr	__ICircleLoop+2
__ICircleEnd:

;Bit
;-----------------------------------------------
p_GetBit:
	.db 12
	ld	a,e
	and	%00000111
	inc	a
	ld	b,a
	xor	a
__GetBitLoop:
	ld	h,a
	add	hl,hl
	djnz	__GetBitLoop
	ld	l,h
	ld	h,b

p_GetBit16:
	.db 12
	ld	a,e
	and	%00001111
	inc	a
	ld	b,a
__GetBit16Loop:
	add	hl,hl
	djnz	__GetBit16Loop
	ld	h,b
	ld	l,b
	rl	l

;Interrupts
;-----------------------------------------------
p_Halt:
	.db 1
	halt
p_FnOn:
	.db 1
	ei
p_FnOff:
	.db 1
	di
p_IntOff:
	.db 2
	im	1
p_IntOffCleanUp:
	.db	17
	im	1
	set	reTable,(iy+tblFlags)
	ld	hl,$8686-($9300-$929F+1)
	ld	de,$929F
	ld	bc,$9300-$929F+1
	ldir
	

p_IntSetup:
	.db __IntSetupEnd-p_IntSetup-1
	di

	ld	de,$8686-($9300-$929F+1)
	ld	a,d
	and	l
	out	(4),a

	ld	hl,$929F
	ld	a,h
	ld	i,a

	ld	bc,$9300-$929F+1
	ldir
	

	ld	hl,$0000
	ld	c,__IntDataEnd-__IntData
	ldir

	inc	b
	ld	h,a
	ld	l,c
	ld	(hl),d
	ld	d,a
	ld	e,b
	ldir

	in	a,(6)
	ld	($8686+__IntDataSMC-__IntData+1),a
__IntSetupEnd:
	.db rp_Ans,19

p_IntPart2:
	.db __IntPart2End-p_IntPart2-1
	ld	hl,$0000
	ld	($8686+__IntDataRep-__IntData+1),hl
	im	2
	call	$8686
__IntPart2End:
	.db rp_Ans,10

;Special interrupt added as data, not routine.
__IntData:
	ex	af,af'
	exx
	push	ix
	ld	a,%11110101
	out	(3),a
	cpl
	out	(3),a
	in	a,(6)
	push	af
__IntDataSMC:
	ld	a,$00
	out	(6),a
__IntDataRep:
	call	$0000
	pop	af
	out	(6),a
	pop	ix
	exx
	ex	af,af'
	ei
	ret
__IntDataEnd:

;Masked Sprite Drawing
;----------------------------------------------------------------------------------
p_DrawMsk:
	.db __DrawMskEnd-1-$
	ex	(sp),hl
	pop	ix			;Input hl = Sprite
	pop	de
	pop	bc
	push	hl
	ld	hl,plotSScreen
x_DrawMskEntry:
	ld	d,7
	ld	a,e
	add	a,d
	jr	c,__DrawMskClipTop
	sub	64+7
	ret	nc
	cpl
	cp	d
	jr	c,__DrawMskClipBottom
	ld	b,d
	jr	__DrawMskNoClipV
__DrawMskClipTop:
	inc	ix
	inc	e
	jr	nz,__DrawMskClipTop
__DrawMskClipBottom:
	ld	b,a
__DrawMskNoClipV:
	ld	a,c
	add	a,d
	cp	96+7
	ret	nc
	rrca
	rrca
	rrca
	and	$1f
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	add	hl,de
	add	hl,de
	ld	e,a
	add	hl,de
	inc	b
	ld	a,c
	and	7
	jr	z,__DrawMskAligned
	ld	e,c
	ld	c,a
	ld	a,e
	cp	-7
	jr	nc,__DrawMskLoop
	inc	d
	cp	96-7
	jr	nc,__DrawMskLoop
	inc	d

__DrawMskLoop:
	push	bc

	push	hl

	ld	b,c
	ld	e,(ix+0)
	xor	a
	ld	h,a
	ld	c,(ix+8)
__DrawMskShift:
	srl	e
	rr	h
	srl	c
	rra
	djnz	__DrawMskShift

	ld	b,h
	pop	hl
	push	af

	dec	d
	jr	z,__DrawMskSkipRight1

	push	bc
	xor	b
	cpl
	ld	c,a

	ld	a,(hl)
	or	b
	and	c
	ld	(hl),a
	pop	bc

__DrawMskSkipRight1:
	dec	hl
	inc	d
	push	de
	jr	z,__DrawMskSkipLeft1

	ld	a,c
	xor	e
	cpl
	ld	d,a

	ld	a,(hl)
	or	e
	and	d
	ld	(hl),a

__DrawMskSkipLeft1:
	ld	de,appBackUpScreen-plotSScreen+1
	add	hl,de
	pop	de
	pop	af
	dec	d
	jr	z,__DrawMskSkipRight2

	or	b
	cpl

	and	(hl)
	or	b
	ld	(hl),a

__DrawMskSkipRight2:
	dec	hl
	inc	d
	jr	z,__DrawMskSkipLeft2

	ld	a,c
	or	e
	cpl

	and	(hl)
	or	e
	ld	(hl),a

__DrawMskSkipLeft2:
	ld	bc,plotSScreen-appBackUpScreen+13
	add	hl,bc

	inc	ix
	pop	bc
	djnz	__DrawMskLoop
	ret
__DrawMskAligned:
	push	hl
	ld	de,appBackUpScreen-plotSScreen
	add	hl,de

	ld	a,(ix+0)
	ld	d,a
	xor	(ix+8)
	cpl
	ld	e,a

	and	(hl)
	or	d
	ld	(hl),a

	pop	hl

	ld	a,(hl)
	or	d
	and	e
	ld	(hl),a

	inc	ix
	ld	de,12
	add	hl,de
	djnz	__DrawMskAligned
	ret
__DrawMskEnd:

p_DrawMsk2:
	.db __DrawMsk2End-1-$
	ex	(sp),hl
	pop	ix			;Input hl = Sprite
	pop	de
	pop	bc
	push	hl
	ld	hl,plotSScreen
x_DrawMsk2Entry:
	ld	d,7
	ld	a,e
	add	a,d
	jr	c,__DrawMsk2ClipTop
	sub	64+7
	ret	nc
	cpl
	cp	d
	jr	c,__DrawMsk2ClipBottom
	ld	b,d
	jr	__DrawMsk2NoClipV
__DrawMsk2ClipTop:
	inc	ix
	inc	e
	jr	nz,__DrawMsk2ClipTop
__DrawMsk2ClipBottom:
	ld	b,a
__DrawMsk2NoClipV:
	ld	a,c
	add	a,d
	cp	96+7
	ret	nc
	rrca
	rrca
	rrca
	and	$1f
	ld	d,0
	sla	e
	sla	e
	add	hl,de
	add	hl,de
	add	hl,de
	ld	e,a
	add	hl,de
	inc	b
	ld	a,c
	and	7
	jr	z,__DrawMsk2Aligned
	ld	e,c
	ld	c,a
	ld	a,e
	cp	-7
	jr	nc,__DrawMsk2Loop
	inc	d
	cp	96-7
	jr	nc,__DrawMsk2Loop
	inc	d
__DrawMsk2Loop:
	push	bc
	push	hl

	ld	b,c
	ld	e,(ix+0)
	xor	a
	ld	h,a
	ld	c,(ix+8)
__DrawMsk2Shift:
	srl	e
	rr	h
	srl	c
	rra
	djnz	__DrawMsk2Shift

	ld	b,h			;e = left spr, b = right spr, c = left msk, a = right msk
	pop	hl

	dec	d
	jr	z,__DrawMsk2SkipRight

	cpl
	and	(hl)
	xor	b
	ld	(hl),a

__DrawMsk2SkipRight:
	dec	hl
	inc	d
	jr	z,__DrawMsk2SkipLeft

	ld	a,c
	cpl
	and	(hl)
	xor	e
	ld	(hl),a

__DrawMsk2SkipLeft:
	ld	bc,13
	add	hl,bc

	inc	ix
	pop	bc
	djnz	__DrawMsk2Loop
	ret
__DrawMsk2Aligned:
	ld	e,12
__DrawMsk2AlignedLoop:
	ld	a,(ix+8)
	cpl
	and	(hl)
	xor	(ix+0)
	ld	(hl),a
	inc	ix
	add	hl,de
	djnz	__DrawMsk2AlignedLoop
	ret
__DrawMsk2End:

p_DrawMskSteal:
	.db 4
	pop	ix
	pop	de
	pop	bc

;Sprite Flipping
;-----------------------------------------------
p_FlipV:
	.db __FlipVEnd-1-$
	ex	de,hl
	ld	hl,vx_SptBuff+8
	ld	b,8
__FlipVLoop:
	dec	l
	ld	a,(de)
	ld	(hl),a
	inc	de
	djnz	__FlipVLoop
	ret
__FlipVEnd:

p_FlipH:
	.db __FlipHEnd-1-$
	ld	de,vx_SptBuff
	push	de
	ld	b,8
__FlipHLoop1:
	ld	c,(hl)
	ld	a,1
__FlipHLoop2:
	rr	c
	rla
	jr	nc,__FlipHLoop2
	ld	(de),a
	inc	e
	inc	hl
	djnz	__FlipHLoop1
	pop	hl
	ret
__FlipHEnd:

p_RotC:
	.db __RotCEnd-1-$
	ex	de,hl
	ld	c,8
__RotCLoop1:
	ld	hl,vx_SptBuff+8
	ld	b,8
	ld	a,(de)
__RotCLoop2:
	dec	l
	rra
	rr	(hl)
	djnz	__RotCLoop2
	inc	de
	dec	c
	jr	nz,__RotCLoop1
	ret
__RotCEnd:

p_RotCC:
	.db __RotCCEnd-1-$
	ex	de,hl
	ld	c,8
__RotCCLoop1:
	ld	hl,vx_SptBuff+8
	ld	b,8
	ld	a,(de)
__RotCCLoop2:
	dec	l
	rla
	rl	(hl)
	djnz	__RotCCLoop2
	inc	de
	dec	c
	jr	nz,__RotCCLoop1
	ret
__RotCCEnd:

;Floating Point Functions
;-----------------------------------------------
p_FtoD:
	.db 5
	rst	20h
	B_CALL(_ConvOP1)
	ex	de,hl

p_DtoF:
	.db 11
	ex	(sp),hl
	B_CALL(_SetXXXXOP2)
	ld	hl,OP2
	pop	de
	B_CALL(_Mov9B)

p_StoreAns:
	.db 9
	B_CALL(_SetXXXXOP2)
	B_CALL(_OP2toOP1)
	B_CALL(_StoAns)

p_RecalAns:
	.db 7
	B_CALL(_RclAns)
	B_CALL(_ConvOP1)
	ex	de,hl

;Safety stuff (Stupid TI/z80!)
;-----------------------------------------------
p_Safety:			;Output: af holds state to-be-pushed
	.db __SafetyEnd-1-$	;DESTROYS B, all other registers okay.
	in	a,($02)		;Save model settings
	rla			;BE flag into carry
	sbc	a,a		;00 if BE else FF
	jr	z,__SafetyBE	;Check If model is base edition
	in	a,($20)		;Get current speed setting
__SafetyBE:
	ld	b,a		;Save speed setting
	xor	a		;Set nc (interrupts)
	out	($20),a		;Set speed to slow
__SafetyIntOnly:
	push	af		;Check interrupts
	pop	af
	ld	a,i		;pe if interrupt
	di
	ld	a,b		;Restore speed setting
	ret	pe		;Return if interrupts on
	dec	sp		;Otherwise, robust test
	dec	sp
	pop	af
	or	a		;Set nc (interrupts)
	ld	a,b
	ret	nz		;Return if interrupts on
	scf			;Set c (no interrupts)
	ret			;Return
__SafetyEnd:

;Other Misc Stuff
;-----------------------------------------------
p_Pause:
	.db 7
	djnz	$+0
	dec	hl
	ld	a,l
	or	h
	jr	nz,$-5

p_Rand:
	.db __RandEnd-1-$
	ld	hl,(vx_Seed)
	ld	a,r
	ld	d,a
	ld	e,(hl)
	add	hl,de
	ld	e,a
	add	hl,de
	ld	(vx_Seed),hl
	ret
__RandEnd:

;############################
;#  Peephole Optimizations  #
;############################
;Rules:
;  Only one $0000 can end up in replacement
;  Replacement $0000 must equal or precede the original position
;-----------------------------------------------

o_BetterZero1:
	.db 3
	ld	l,a
	ld	a,h
	or	l
	.db 2
	ld	l,a
	or	h
o_BetterZero2:
	.db 3
	ld	h,0
	ld	a,h
	or	l
	.db 3
	xor	a
	ld	h,a
	or	l
o_BetterZero3:
	.db 3
	sbc	hl,de
	ld	a,h
	or	l
	.db 2
	sbc	hl,de
o_BetterZero4:
	.db 3
	sbc	hl,hl
	ld	a,h
	or	l
	.db 2
	sbc	hl,hl
o_BetterZero5:
	.db 4
	ld	l,a
	ld	h,a
	ld	a,h
	or	l
	.db 3
	ld	l,a
	ld	h,a
	or	l
o_BetterZero6:
	.db 7
	xor	a
	ld	h,a
	inc	a
	and	l
	ld	l,a
	ld	a,h
	or	l
	.db 5
	xor	a
	ld	h,a
	inc	a
	and	l
	ld	l,a
o_BetterZero7:
	.db 7
	ld	l,a
	pop	de
	ld	a,l
	or	e
	ld	l,a
	ld	a,h
	or	l
	.db 4
	pop	de
	or	e
	ld	l,a
	or	h
o_BetterZero8:
	.db 8
	xor	a
	sbc	hl,de
	ld	l,a
	ld	h,a
	jr	$+3
	inc	l
	ld	a,h
	or	l
	.db 9
	xor	a
	sbc	hl,de
	ld	l,a
	ld	h,a
	jr	nz,$+3
	inc	l
	or	l
o_BetterZero9:
	.db 8
	sbc	hl,hl
	inc	hl
	pop	de
	ld	a,l
	and	e
	ld	l,a
	ld	a,h
	or	l
	.db 7
	sbc	hl,hl
	inc	hl
	pop	de
	ld	a,l
	and	e
	ld	l,a

o_ShortOpt1:
	.db 5
	ld	h,0
	pop	de
	ex	de,hl
	or	a
	sbc	hl,de
	.db 6
	xor	a
	ld	h,a
	pop	de
	ex	de,hl
	sbc	hl,de
o_ShortOpt2:
	.db 6
	ld	h,0
	ld	a,l
	or	h
	add	a,255
	sbc	hl,hl
	inc	hl
	.db 5
	xor	a
	cp	l
	sbc	hl,hl
	inc	hl

o_PushPop1:
	.db 2
	push	bc
	pop	bc
	.db 0
o_PushPop2:
	.db 2
	push	hl
	pop	de
	.db 2
	ld	d,h
	ld	e,l
o_PushPop3:
	.db 3
	push	hl
	ld	hl,$0000
	pop	de
	.db 4
	ex	de,hl
	ld	hl,$0000
o_PushPop4:
	.db 3
	push	hl
	ld	hl,($0000)
	pop	de
	.db 4
	ex	de,hl
	ld	hl,($0000)
;o_PushPop5:
;	.db 3
;	ld	hl,$0000
;	push	hl
;	ld	hl,$0000
;	.db 4
;	ld	hl,$0000
;	push	hl
o_PushPop6:
	.db 3
	ld	hl,($0000)
	push	hl
	ld	hl,($0000)
	.db 4
	ld	hl,($0000)
	push	hl
o_PushPop7:
	.db 4
	ld	h,0
	push	hl
	ld	hl,($0000)
	ld	h,0
	.db 7
	ld	h,0
	push	hl
	ld	a,($0000)
	ld	l,a
o_PushPop8:
	.db 6
	push	hl
	ld	hl,$0000
	pop	de
	ex	(sp),hl
	pop	bc
	ldir
	.db 7
	ld	bc,$0000
	ex	de,hl
	pop	hl
	ldir
o_PushPop9:
	.db 6
	push	hl
	ld	hl,($0000)
	pop	de
	ex	(sp),hl
	pop	bc
	ldir
	.db 8
	ld	bc,($0000)
	ex	de,hl
	pop	hl
	ldir
o_PushPop10:
	.db 6
	push	hl
	ld	hl,$0000
	pop	de
	ex	(sp),hl
	pop	bc
	lddr
	.db 7
	ld	bc,$0000
	ex	de,hl
	pop	hl
	lddr
o_PushPop11:
	.db 6
	push	hl
	ld	hl,($0000)
	pop	de
	ex	(sp),hl
	pop	bc
	lddr
	.db 8
	ld	bc,($0000)
	ex	de,hl
	pop	hl
	lddr
o_PushPop12:
	.db 4
	push	hl
	ld	hl,$0000
	ex	de,hl
	pop	hl
	.db	3
	ld	de,$0000
o_PushPop13:
	.db 4
	push	hl
	ld	hl,($0000)
	ex	de,hl
	pop	hl
	.db	4
	ld	de,($0000)

o_CallOpt1:
	.db 2
	ret
	ret
	.db 1
	ret

o_Contrast1:
	.db 5
	ld	l,a
	ld	h,0
	ld	a,l
	or	%11000000
	out	($10),a
	.db 4
	or	%11000000
	out	($10),a

o_ReLoad1:
	.db 2
	ld	($0000),hl
	ld	hl,($0000)
	.db 3
	ld	($0000),hl
o_ReLoad2:
	.db 3
	ld	($0000),a
	ld	hl,($0000)
	ld	h,0
	.db 6
	ld	($0000),a
	ld	h,0
	ld	l,a
o_ReLoad3:
	.db 4
	ld	a,l
	ld	($0000),a
	ld	hl,($0000)
	ld	h,0
	.db 6
	ld	a,l
	ld	($0000),a
	ld	h,0

o_AddSub1:
	.db 2
	inc	hl
	dec	hl
	.db 0
o_AddSub2:
	.db 5
	ld	h,0
	ld	a,($0000)
	ld	e,a
	ld	d,0
	add	hl,de
	.db 8
	ld	a,($0000)
	ld	h,0
	ld	d,h
	ld	e,a
	add	hl,de
o_AddSub3:
	.db 6
	ld	h,0
	ld	a,($0000)
	ld	e,a
	ld	d,0
	or	a
	sbc	hl,de
	.db 8
	ld	a,l
	ld	hl,($0000)
	sub	l
	ld	l,a
	sbc	a,a
	ld	h,a
o_AddSub4:
	.db 7
	ld	l,(hl)
	ld	h,0
	ld	a,($0000)
	ld	e,a
	ld	d,0
	or	a
	sbc	hl,de
	.db 8
	ld	a,(hl)
	ld	hl,($0000)
	sub	l
	ld	l,a
	sbc	a,a
	ld	h,a

o_Neg1:
	.db 7
	ld	h,0
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	sub	h
	ld	h,a
	.db 5
	xor	a
	sub	l
	ld	l,a
	sbc	a,a
	ld	h,a