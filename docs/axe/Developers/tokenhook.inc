;TI-83/84 Plus Token Hook Include File
;09/02/2012
;Compiled by Zachary Wassall (runer112@gmail.com)

;TOKEN HOOK BASICS
;-------------------------------------------------------
;Hook must start with .db 83h
;
;To set hook, load page into A (0 for RAM), load pointer
;  into HL, and B_CALL(_SetTokenHook)
;
;Value is passed in DE, or BC with DE=hExtend for new
;  tokens in 1.16+
;
;To use default string, return with HL preserved
;
;To replace string, copy the custom length-prefixed
;  string (1 byte length) to localTokStr+1 and return
;  with HL=localTokStr * DO NOT OVERWRITE (localTokStr) *

.nolist
#include "ti83plus.inc"
.list

;Tokens
;-------------------------------------------------------
hUnused00		equ 000h

hToDMS			equ 002h ;Lconvert,"DMS"
hToDEC			equ 004h ;Lconvert,"Dec"
hToAbc			equ 006h ;Lconvert,"Frac"

hStore			equ 008h ;Lstore

hBoxPlot		equ 00Ah ;"Boxplot"

hLBrack			equ 00Ch ;LlBrack
hRBrack			equ 00Eh ;"]"
hLBrace			equ 010h ;"{"
hRBrace			equ 012h ;"}"

hFromRad		equ 014h ;Lradian
hFromDeg		equ 016h ;Ldegree
hRecip			equ 018h ;Linverse
hSqr			equ 01Ah ;Lsquare
hTrnspos		equ 01Ch ;Ltranspose
hCube			equ 01Eh ;Lcube

hLParen			equ 020h ;"("
hRParen			equ 022h ;")"

hRound			equ 024h ;"round("
hPxTst			equ 026h ;"pxl-Test("
hAug			equ 028h ;"augment("
hRowSwap		equ 02Ah ;"rowSwap("
hRowPlus		equ 02Ch ;"row+("
hmRow			equ 02Eh ;"*row("
hmRowPlus		equ 030h ;"*row+("
hMax			equ 032h ;"max("
hMin			equ 034h ;"min("
hRToPr			equ 036h ;"R",Lconert,"Pr"
hRToPo			equ 038h ;"R"Lconvert,"P",Ltheta
hPToRx			equ 03Ah ;"P",Lconert,"Rx"
hPToRy			equ 03Ch ;"P",Lconert,"Ry"
hMedian			equ 03Eh ;"median("
hRandM			equ 040h ;"randM("
hMean			equ 042h ;"mean("
hRoot			equ 044h ;"solve("
hSeries			equ 046h ;"seq("
hFnInt			equ 048h ;"fnInt("
hNDeriv			equ 04Ah ;"nDeriv("
hUnused01		equ 04Ch
hFmin			equ 04Eh ;"fMin("
hFmax			equ 050h ;"fMax"

hSpace			equ 052h ;" "
hString			equ 054h ;Lquote
hComma			equ 056h ;","

hii			equ 058h ;LimagI

;Postfix Functions
;-------------------------------------------------------
hFact			equ 05Ah ;"!"

hCubicR			equ 05Ch ;"CubicReg "
hQuartR			equ 05Eh ;"QuartReg "

;Number Tokens 
;-------------------------------------------------------
h0			equ 060h ;"0"
h1			equ 062h ;"1"
h2			equ 064h ;"2"
h3			equ 066h ;"3"
h4			equ 068h ;"4"
h5			equ 06Ah ;"5"
h6			equ 06Ch ;"6"
h7			equ 06Eh ;"7"
h8			equ 070h ;"8"
h9			equ 072h ;"9"
hDecPt			equ 074h ;"."
hee			equ 076h ;Lexponent

;Binary OP
;-------------------------------------------------------
hOr			equ 078h ;" or "
hXor			equ 07Ah ;" xor "

hColon			equ 07Ch ;":"
hEnter			equ 07Eh ;Lenter

hAnd			equ 080h ;" and "

;Letter Tokens
;-------------------------------------------------------
hA			equ 082h ;"A"
hB			equ 084h ;"B"
hC			equ 086h ;"C"
hD			equ 088h ;"D"
hE			equ 08Ah ;"E"
hF			equ 08Ch ;"F"
hG			equ 08Eh ;"G"
hH			equ 090h ;"H"
hI			equ 092h ;"I"
hJ			equ 094h ;"J"
hK			equ 096h ;"K"
hL			equ 098h ;"L"
hM			equ 09Ah ;"M"
hN			equ 09Ch ;"N"
hO			equ 09Eh ;"O"
hP			equ 0A0h ;"P"
hQ			equ 0A2h ;"Q"
hR			equ 0A4h ;"R"
hS			equ 0A6h ;"S"
hT			equ 0A8h ;"T"
hU			equ 0AAh ;"U"
hV			equ 0ACh ;"V"
hW			equ 0AEh ;"W"
hX			equ 0B0h ;"X"
hY			equ 0B2h ;"Y"
hZ			equ 0B4h ;"Z"
hTheta			equ 0B6h ;Ltheta

;These Var Tokens Are 1st Of A Double Token
;-------------------------------------------------------
;User Matrix Token, 2nd Token Needed For Name
;User List Token, 2nd Token Needed For Name
;User Equation Token, 2nd Token Needed For Name

hProg			equ 0BEh ;"prgm"

;User Pict Token, 2nd Token Needed For Name
;User GDB Token, 2nd Token Needed For Name
;System Output Only Variables, 2nd Token Needed For Name
;System Input/Output Variables, 2nd Token Needed For Name

;Mode Setting Commands
;-------------------------------------------------------
hRad			equ 0C8h ;"Radian"
hDeg			equ 0CAh ;"Degree"
hNormF			equ 0CCh ;"Normal"
hSci			equ 0CEh ;"Sci"
hEng			equ 0D0h ;"Eng"
hFloat			equ 0D2h ;"Float"

hEQ			equ 0D4h ;"="
hLT			equ 0D6h ;"<"
hGT			equ 0D8h ;">"
hLE			equ 0DAh ;LLE
hGE			equ 0DCh ;LGE
hNE			equ 0DEh ;LNE

;Binary OP
;-------------------------------------------------------
hAdd			equ 0E0h ;"+"
hSub			equ 0E2h ;"-"
hAns			equ 0E4h ;"Ans"

;Mode Setting Commands
;-------------------------------------------------------
hFix			equ 0E6h ;"Fix "
hSplitOn		equ 0E8h ;"Horiz"
hFullScreen		equ 0EAh ;"Full"
hStndrd			equ 0ECh ;"Func"
hParam			equ 0EEh ;"Param"
hPolar			equ 0F0h ;"Pol"
hSeqG			equ 0F2h ;"Seq"
hAFillOn		equ 0F4h ;"IndpntAuto"
hAFillOff		equ 0F6h ;"IndpntAsk"
hACalcOn		equ 0F8h ;"DependAuto"
hACalcOff		equ 0FAh ;"DependAsk"

;Graph Format Token, 2nd Token Needed For Name

hBoxIcon		equ 0FEh ;LboxIcon
hCrossIcon		equ 100h ;LcrossIcon
hDotIcon		equ 102h ;LdotIcon

;(More) Binary OP
;-------------------------------------------------------
hMul			equ 104h ;"*"
hDiv			equ 106h ;"/"

;Some Graph Commands
;-------------------------------------------------------
hTrace			equ 108h ;"Trace"
hClDrw			equ 10Ah ;"ClrDraw"
hZoomStd		equ 10Ch ;"ZStandard"
hZoomTrg		equ 10Eh ;"ZTrig"
hZoomBox		equ 110h ;"ZBox"
hZoomIn			equ 112h ;"Zoom In"
hZoomOut		equ 114h ;"Zoom Out"
hZoomSqr		equ 116h ;"ZSquare"
hZoomInt		equ 118h ;"ZInteger"
hZoomPrev		equ 11Ah ;"ZPrevious"
hZoomDec		equ 11Ch ;"ZDecimal"
hZoomStat		equ 11Eh ;"ZoomStat"
hUsrZm			equ 120h ;"ZoomRcl"
hPrtScrn		equ 122h ;"PrintScreen"
hZoomSto		equ 124h ;"ZoomSto"
hText			equ 126h ;"Text("

;Binary OP (Combination & Permutation)
;-------------------------------------------------------
hnPr			equ 128h ;" nPr "
hnCr			equ 12Ah ;" nCr "

;More Graph Commands
;-------------------------------------------------------
hYOn			equ 12Ch ;"FnOn "
hYOff			equ 12Eh ;"FnOff "
hStPic			equ 130h ;"StorePic "
hRcPic			equ 132h ;"RecallPic "
hStoDB			equ 134h ;"StoreGDB "
hRclDB			equ 136h ;"RecallGDB "
hLine			equ 138h ;"Line("
hVert			equ 13Ah ;"Vertical "
hPtOn			equ 13Ch ;"Pt-On("
hPtOff			equ 13Eh ;"Pt-Off("

;Token A0 Cannot Be An EOS Function Since Low MULT=A0 Already
;-------------------------------------------------------
hPtChg			equ 140h ;"Pt-Change("
hPXOn			equ 142h ;"Pxl-On("
hPXOff			equ 144h ;"Pxl-Off("
hPXChg			equ 146h ;"Pxl-Change("
hShade			equ 148h ;"Shade("
hCircl			equ 14Ah ;"Circle("
hHorz			equ 14Ch ;"Horizontal "
hTanLn			equ 14Eh ;"Tangent("
hDrInv			equ 150h ;"DrawInv "
hDrawF			equ 152h ;"DrawF "

;User String Token, 2nd Token Needed For Name

;Functions with No Arguments                                    
;--------------------------------------------
hRand			equ 156h ;"rand"
hPi			equ 158h ;Lpi
hGetKey			equ 15Ah ;"getKey"

hAPost			equ 15Ch ;Lapostophe
hQuest			equ 15Eh ;"?"

hChs			equ 160h ;"Lneg"
hInt			equ 162h ;"int("
hAbs			equ 164h ;"abs("
hDet			equ 166h ;"det("
hIdent			equ 168h ;"identity("
hDim			equ 16Ah ;"dim("
hSum			equ 16Ch ;"sum("
hProd			equ 16Eh ;"prod("
hNot			equ 170h ;"not("
hIPart			equ 172h ;"iPart("
hFPart			equ 174h ;"fPart("

;New 2 Byte Tokens
;----------------------------------------------------
;t2ByteTok Token, 2nd Token Needed For Name

hSqrt			equ 178h ;Lroot,"("
hCubRt			equ 17Ah ;LcubeR,Lroot,"("
hLn			equ 17Ch ;"ln("
hExp			equ 17Eh ;Llne,"^("
hLog			equ 180h ;"log("
hALog			equ 182h ;Lten,"^("
hSin			equ 184h ;"sin("
hASin			equ 186h ;"sin",Linverse,"("
hCos			equ 188h ;"cos("
hACos			equ 18Ah ;"cos",Linverse,"("
hTan			equ 18Ch ;"tan("
hATan			equ 18Eh ;"tan",Linverse,""
hSinH			equ 190h ;"sinh("
hASinH			equ 192h ;"sinh",Linverse,"("
hCoshH			equ 194h ;"cosh("
hACosH			equ 196h ;"cosh",Linverse,"("
hTanH			equ 198h ;"tanh("
hATanH			equ 19Ah ;"tanh",Linverse,"("

;Some Programming Commands
;--------------------------------------------
hIf			equ 19Ch ;"If "
hThen			equ 19Eh ;"Then"
hElse			equ 1A0h ;"Else"
hWhile			equ 1A2h ;"While "
hRepeat			equ 1A4h ;"Repeat "
hFor			equ 1A6h ;"For("
hEnd			equ 1A8h ;"End"
hReturn			equ 1AAh ;"Return"
hLbl			equ 1ACh ;"Lbl "
hGoto			equ 1AEh ;"Goto "
hPause			equ 1B0h ;"Pause "
hStop			equ 1B2h ;"Stop"
hISG			equ 1B4h ;"IS>("
hDSL			equ 1B6h ;"DS<("
hInput			equ 1B8h ;"Input "
hPrompt			equ 1BAh ;"Prompt "
hDisp			equ 1BCh ;"Disp "
hDispG			equ 1BEh ;"DispGraph"

hOutput			equ 1C0h ;"Output("
hClLCD			equ 1C2h ;"ClrHome"
hConst			equ 1C4h ;"Fill("
hSortA			equ 1C6h ;"SortA("
hSortD			equ 1C8h ;"SortD("
hDispTab		equ 1CAh ;"DispTable"
hMenu			equ 1CCh ;"Menu("
hSendMBL		equ 1CEh ;"Send("
hGetMBL			equ 1D0h ;"Get("

;Stat Plot Commands
;------------------------------------------------
hPlotOn			equ 1D2h ;"PlotsOn "
hPlotOff		equ 1D4h ;"PlotsOff "

hListName		equ 1D6h ;LlistL

hPlot1			equ 1D8h ;"Plot1("
hPlot2			equ 1DAh ;"Plot2("
hPlot3			equ 1DCh ;"Plot3("

;84 Plus Only Token, 2nd Token Needed For Name

hPower			equ 1E0h ;"^"
hXRoot			equ 1E2h ;LsupX,Lroot

hOneVar			equ 1E4h ;"1-Var Stats "
hTwoVar			equ 1E6h ;"2-Var Stats "
hLR			equ 1E8h ;"LinReg(a+bx) "
hLRExp			equ 1EAh ;"ExpReg "
hLRLn			equ 1ECh ;"LnReg "
hLRPwr			equ 1EEh ;"PwrReg "
hMedMed			equ 1F0h ;"Med-Med "
hQuad			equ 1F2h ;"QuadReg "
hClrLst			equ 1F4h ;"ClrList "
hClrTbl			equ 1F6h ;"ClrTable"
hHist			equ 1F8h ;"Histogram"
hxyLine			equ 1FAh ;"xyLine"
hScatter		equ 1FCh ;"Scatter"
hLR1			equ 1FEh ;"LinReg(ax+b) "

;2nd Half Of User Matrix Tokens
;---------------------------------------------
hMatA			equ 200h ;LlBrack,"A]"
hMatB			equ 202h ;LlBrack,"B]"
hMatC			equ 204h ;LlBrack,"C]"
hMatD			equ 206h ;LlBrack,"D]"
hMatE			equ 208h ;LlBrack,"E]"
hMatF			equ 20Ah ;LlBrack,"F]"
hMatG			equ 20Ch ;LlBrack,"G]"
hMatH			equ 20Eh ;LlBrack,"H]"
hMatI			equ 210h ;LlBrack,"I]"
hMatJ			equ 212h ;LlBrack,"J]"

;2nd Half Of User List Tokens
;------------------------------------------
hL1			equ 214h ;"L",Lsub1
hL2			equ 216h ;"L",Lsub2
hL3			equ 218h ;"L",Lsub3
hL4			equ 21Ah ;"L",Lsub4
hL5			equ 21Ch ;"L",Lsub5
hL6			equ 21Eh ;"L",Lsub6

;2nd Half Of User Equation Tokens
;------------------------------------------------
;"Y" Equations Have Bit 4 Set

hY1			equ 220h ;"Y",Lsub1
hY2			equ 222h ;"Y",Lsub2
hY3			equ 224h ;"Y",Lsub3
hY4			equ 226h ;"Y",Lsub4
hY5			equ 228h ;"Y",Lsub5
hY6			equ 22Ah ;"Y",Lsub6
hY7			equ 22Ch ;"Y",Lsub7
hY8			equ 22Eh ;"Y",Lsub8
hY9			equ 230h ;"Y",Lsub9
hY0			equ 232h ;"Y",Lsub0

;Param Equations Have Bit 5 Set

hX1T			equ 234h ;"X",Lsub1,LsubT
hY1T			equ 236h ;"Y",Lsub1,LsubT
hX2T			equ 238h ;"X",Lsub2,LsubT
hY2T			equ 23Ah ;"Y",Lsub2,LsubT
hX3T			equ 23Ch ;"X",Lsub3,LsubT
hY3T			equ 23Eh ;"Y",Lsub3,LsubT
hX4T			equ 240h ;"X",Lsub4,LsubT
hY4T			equ 242h ;"Y",Lsub4,LsubT
hX5T			equ 244h ;"X",Lsub5,LsubT
hY5T			equ 246h ;"Y",Lsub5,LsubT
hX6T			equ 248h ;"X",Lsub6,LsubT
hY6T			equ 24Ah ;"Y",Lsub6,LsubT

;Polar Equations Have Bit 6 Set

hR1			equ 24Ch ;"r",Lsub1
hR2			equ 24Eh ;"r",Lsub2
hR3			equ 250h ;"r",Lsub3
hR4			equ 252h ;"r",Lsub4
hR5			equ 254h ;"r",Lsub5
hR6			equ 256h ;"r",Lsub6

;Recursion Equations Have Bit 7 Set

hun			equ 258h ;"u"
hvn			equ 25Ah ;"v"
hwn			equ 25Ch ;"w"

;2nd Half Of User Picture Tokens
;---------------------------------------
hPic1			equ 25Eh ;"Pic1"
hPic2			equ 260h ;"Pic2"
hPic3			equ 262h ;"Pic3"
hPic4			equ 264h ;"Pic4"
hPic5			equ 266h ;"Pic5"
hPic6			equ 268h ;"Pic6"
hPic7			equ 26Ah ;"Pic7"
hPic8			equ 26Ch ;"Pic8"
hPic9			equ 26Eh ;"Pic9"
hPic0			equ 270h ;"Pic0"

;2nd Half Of User Graph Database Tokens
;---------------------------------------
hGDB1			equ 272h ;"GDB1"
hGDB2			equ 274h ;"GDB2"
hGDB3			equ 276h ;"GDB3"
hGDB4			equ 278h ;"GDB4"
hGDB5			equ 27Ah ;"GDB5"
hGDB6			equ 27Ch ;"GDB6"
hGDB7			equ 27Eh ;"GDB7"
hGDB8			equ 280h ;"GDB8"
hGDB9			equ 282h ;"GDB9"
hGDB0			equ 284h ;"GDB0"

;2nd Half Of String Vars
;---------------------------------------
hStr1			equ 286h ;"Str1"
hStr2			equ 288h ;"Str2"
hStr3			equ 28Ah ;"Str3"
hStr4			equ 28Ch ;"Str4"
hStr5			equ 28Eh ;"Str5"
hStr6			equ 290h ;"Str6"
hStr7			equ 292h ;"Str7"
hStr8			equ 294h ;"Str8"
hStr9			equ 296h ;"Str9"
hStr0			equ 298h ;"Str0"

;2nd Half Of System Output Only Variables
;------------------------------------------------------------
hUnused02		equ 29Ah
hRegEq			equ 29Ch ;"RegEQ"
hStatN			equ 29Eh ;"n"
hXMean			equ 2A0h ;LxMean
hSumX			equ 2A2h ;LcapSigma,"x"
hSumXSqr		equ 2A4h ;Lcapsigma,"x",Lsquare
hStdX			equ 2A6h ;"Sx"
hStdPX			equ 2A8h ;Lsigma,"x"
hMinX			equ 2AAh ;"minX"
hMaxX			equ 2ACh ;"maxX"
hMinY			equ 2AEh ;"minY"
hMaxY			equ 2B0h ;"maxY"
hYmean			equ 2B2h ;LyMean
hSumY			equ 2B4h ;LcapSigma,"y"
hSumYSqr		equ 2B6h ;LcapSigma,"y",Lsquare
hStdY			equ 2B8h ;"Sy"
hStdPY			equ 2BAh ;Lsigma,"y"
hSumXY			equ 2BCh ;LcapSigma,"xy"
hCorr			equ 2BEh ;"r"
hMedX			equ 2C0h ;"Med"
hQ1			equ 2C2h ;"Q",Lsub1
hQ3			equ 2C4h ;"Q",Lsub3
hQuadA			equ 2C6h ;"a"
hQuadB			equ 2C8h ;"b"
hQuadC			equ 2CAh ;"c"
hCubeD			equ 2CCh ;"d"
hQuartE			equ 2CEh ;"e"
hMedX1			equ 2D0h ;"x",Lsub1
hMedX2			equ 2D2h ;"x",Lsub2
hMedX3			equ 2D4h ;"x",Lsub3
hMedY1			equ 2D6h ;"y",Lsub1
hMedY2			equ 2D8h ;"y",Lsub2
hMedY3			equ 2DAh ;"y",Lsub3
hRecurn			equ 2DCh ;LrecurN
hStatP			equ 2DEh ;"p"
hStatZ			equ 2E0h ;"z"
hStatT			equ 2E2h ;"t"
hStatChi		equ 2E4h ;Lchi,Lsquare
hStatF			equ 2E6h ;LstatF
hStatDF			equ 2E8h ;"df"
hStatPhat		equ 2EAh ;Lphat
hStatPhat1		equ 2ECh ;Lphat,Lsub1
hStatPhat2		equ 2EEh ;Lphat,Lsub2
hStatMeanX1		equ 2F0h ;LxMean,Lsub1
hStatStdX1		equ 2F2h ;"Sx",Lsub1
hStatN1			equ 2F4h ;"n",Lsub1
hStatMeanX2		equ 2F6h ;LxMean,Lsub2
hStatStdX2		equ 2F8h ;"Sx",Lsub2
hStatN2			equ 2FAh ;"n",Lsub2
hStatStdXP		equ 2FCh ;"Sxp"
hStatLower		equ 2FEh ;"lower"
hStatUpper		equ 300h ;"upper"
hStat_s			equ 302h ;"s"
hLRSqr			equ 304h ;"r",Lsquare
hBRSqr			equ 306h ;"R",Lsquare

;These next tokens are only used to access the data
;they are display only and the user cannot access them at all

hF_DF			equ 308h ;"df"
hF_SS			equ 30Ah ;"SS"
hF_MS			equ 30Ch ;"MS"
hE_DF			equ 30Eh ;"df"
hE_SS			equ 310h ;"SS"
hE_MS			equ 312h ;"MS"

;2nd Half Of System Input/Output Variables
;------------------------------------------------------

huXscl			equ 314h ;"ZXscl"
huYscl			equ 316h ;"ZYscl"
hXscl			equ 318h ;"Xscl"
hYscl			equ 31Ah ;"Yscl"
hRecuru0		equ 31Ch ;"u(",LrecurN,"Min)"
hRecurv0		equ 31Eh ;"v(",LrecurN,"Min)"
hun1			equ 320h ;"U",LrecurN,"-",Lsub1
hvn1			equ 322h ;"V",LrecurN,"-",Lsub1
huRecuru0		equ 324h ;"Zu(",LrecurN,"Min)"
huRecurv0		equ 326h ;"Zv(",LrecurN,"Min)"
hXmin			equ 328h ;"Xmin"
hXmax			equ 32Ah ;"Xmax"
hYmin			equ 32Ch ;"Ymin"
hYmax			equ 32Eh ;"Ymax"
hTmin			equ 330h ;"Tmin"
hTmax			equ 332h ;"Tmax"
hThetaMin		equ 334h ;Ltheta,"min"
hThetaMax		equ 336h ;Ltheta,"max"
huXmin			equ 338h ;"ZXmin"
huXmax			equ 33Ah ;"ZXmax"
huYmin			equ 33Ch ;"ZYmin"
huYmax			equ 33Eh ;"ZYmax"
huThetMin		equ 340h ;"Z",Ltheta,"min"
huThetMax		equ 342h ;"Z",Ltheta,"max"
huTmin			equ 344h ;"ZTmin"
huTmax			equ 346h ;"ZTmax"
hTblMin			equ 348h ;"TblStart"
hPlotStart		equ 34Ah ;"PlotStart"
huPlotStart		equ 34Ch ;"ZPlotStart"
hnMax			equ 34Eh ;Lrecurn,"Max"
hunMax			equ 350h ;"Z",LrecurN,"Max"
hnMin			equ 352h ;Lrecurn,"Min"
hunMin			equ 354h ;"Z",LrecurN,"Min"
hTblStep		equ 356h ;LcapDelta,"Tbl"
hTStep			equ 358h ;"Tstep"
hThetaStep		equ 35Ah ;Ltheta,"step"
huTStep			equ 35Ch ;"ZTstep"
huThetStep		equ 35Eh ;"Z",Ltheta,"step"
hDeltaX			equ 360h ;LcapDelta,"X"
hDeltaY			equ 362h ;LcapDelta,"Y"
hXFact			equ 364h ;"XFact"
hYFact			equ 366h ;"YFact"
hTblInput		equ 368h ;"TblInput"
hFinN			equ 36Ah ;LfinanN
hFinI			equ 36Ch ;"I",Lpercent
hFinPV			equ 36Eh ;"PV"
hFinPMT			equ 370h ;"PMT"
hFinFV			equ 372h ;"FV"
hFinPY			equ 374h ;"P/Y"
hFinCY			equ 376h ;"C/Y"
hRecurw0		equ 378h ;"w(",LrecurN,"Min)"
huRecurw0		equ 37Ah ;"Zw(",LrecurN,"Min)"
hPlotStep		equ 37Ch ;"PlotStep"
huPlotStep		equ 37Eh ;"PlotStart"
hXres			equ 380h ;"Xres"
huXres			equ 382h ;"ZXres"

;2nd Half Of Graph Format Tokens
;---------------------------------------------

hSeq			equ 384h ;"Sequential"
hSimulG			equ 386h ;"Simul"
hPolarG			equ 388h ;"PolarGC"
hRectG			equ 38Ah ;"RectGC"
hCoordOn		equ 38Ch ;"CoordOn"
hCoordOff		equ 38Eh ;"CoordOff"
hDrawLine		equ 390h ;"Connected"
hDrawDot		equ 392h ;"Dot"
hAxisOn			equ 394h ;"AxesOn"
hAxisOff		equ 396h ;"AxesOff"
hGridOn			equ 398h ;"GridOn"
hGridOff		equ 39Ah ;"GridOff"
hLblOn			equ 39Ch ;"LabelOn"
hLblOff			equ 39Eh ;"LabelOff"
hWebOn			equ 3A0h ;"Web"
hWebOff			equ 3A2h ;"Time"
huv			equ 3A4h ;"uvAxes"
hvw			equ 3A6h ;"vwAxes"
huw			equ 3A8h ;"uwAxes"

;2nd Half Of t2ByteTok Tokens
;-------------------------------
hFinNPV			equ 3AAh ;"npv("
hFinIRR			equ 3ACh ;"irr("
hFinBAL			equ 3AEh ;"bal("
hFinPRN			equ 3B0h ;LcapSigma,"Prn("
hFinINT			equ 3B2h ;LcapSigna,"Int("
hFinToNom		equ 3B4h ;Lconvert,"Nom("
hFinToEff		equ 3B6h ;Lconvert,"Eff("
hFinDBD			equ 3B8h ;"dbd("
hLCM			equ 3BAh ;"lcm"
hGCD			equ 3BCh ;"gcd"
hRandInt		equ 3BEh ;"randInt("
hRandBin		equ 3C0h ;"randBin("
hSubStrng		equ 3C2h ;"sub("
hStdDev			equ 3C4h ;"stdDev("
hVariance		equ 3C6h ;"variance("
hInStrng		equ 3C8h ;"inString("
hDNormal		equ 3CAh ;"normalcdf("
hInvNorm		equ 3CCh ;"invNorm("
hDT			equ 3CEh ;"tcdf("
hChI			equ 3D0h ;Lchi,Lsquare,"cdf("
hDF			equ 3D2h ;LstatF,"cdf("
hBINPDF			equ 3D4h ;"binompdf("
hBINCDF			equ 3D6h ;"binomcdf("
hPOIPDF			equ 3D8h ;"poissonpdf("
hPOICDF			equ 3DAh ;"poissoncdf("
hGEOPDF			equ 3DCh ;"geometpdf("
hGEOCDF			equ 3DEh ;"geometcdf("
hNormalPDF		equ 3E0h ;"normalpdf("
hTPDF			equ 3E2h ;"tpdf("
hChiPDF			equ 3E4h ;Lchi,Lsquare,"pdf("
hFPDF			equ 3E6h ;LstatF,"pdf("
hRandNorm		equ 3E8h ;"randNorm("
hFinFPMT		equ 3EAh ;"tvm_Pmt"
hFinFI			equ 3ECh ;"tvm_I%"
hFinFPV			equ 3EEh ;"tvm_PV"
hFinFN			equ 3F0h ;"tvm_",LfinanN
hFinFFV			equ 3F2h ;"tvm_FV"
hConj			equ 3F4h ;"conj("
hReal			equ 3F6h ;"real("
hImag			equ 3F8h ;"imag("
hAngle			equ 3FAh ;"angle("
hCumSum			equ 3FCh ;"cumSum("
hExpr			equ 3FEh ;"expr("
hLength			equ 400h ;"length("
hDeltaLst		equ 402h ;LcapDelta,"List("
hRef			equ 404h ;"ref("
hRRef			equ 406h ;"rref("
hToRect			equ 408h ;Lconvert,"Rect"
hToPolar		equ 40Ah ;Lconvert,"Polar"
hConste			equ 40Ch ;Llne
hSinReg			equ 40Eh ;"SinReg "
hLogistic		equ 410h ;"Logistic "
hLinRegTTest		equ 412h ;"LinRegTTest "
hShadeNorm		equ 414h ;"ShadeNorm("
hShadeT			equ 416h ;"Shade_t("
hShadeChi		equ 418h ;"Shade",Lchi,Lsquare
hShadeF			equ 41Ah ;"Shade",LstatF
hMatToLst		equ 41Ch ;"Matr",Lconvert,"list("
hLstToMat		equ 41Eh ;"List",Lconvert,"matr("
hZTest			equ 420h ;"Z-Test("
hTTest			equ 422h ;"T-Test("
h2SampZTest		equ 424h ;"2-SampZTest("
h1PropZTest		equ 426h ;"1-PropZTest("
h2PropZTest		equ 428h ;"2-PropZTest("
hChiTest		equ 42Ah ;Lchi,Lsquare,"-Test("
hZIntVal		equ 42Ch ;"ZInterval "
h2SampZInt		equ 42Eh ;"2-SampZInt("
h1PropZInt		equ 430h ;"1-PropZInt("
h2PropZInt		equ 432h ;"2-PropZInt("
hGraphStyle		equ 434h ;"GraphStyle("
h2SampTTest		equ 436h ;"2-SampTTest "
h2SampFTest		equ 438h ;"2-Samp",LstatF,"Test "
hTIntVal		equ 43Ah ;"TInterval "
h2SampTInt		equ 43Ch ;"2-SampTInt "
hSetupLst		equ 43Eh ;"SetUpEditor "
hFinPMTend		equ 440h ;"Pmt_End"
hFinPMTbeg		equ 442h ;"Pmt_Bgn"
hRealM			equ 444h ;"Real"
hPolarM			equ 446h ;"re^",Ltheta,LimagI
hRectM			equ 448h ;"a+b",LimagI
hExprOn			equ 44Ah ;"ExprOn"
hExprOff		equ 44Ch ;"ExprOff"
hClrAllLst		equ 44Eh ;"ClrAllLists"
hGetCalc		equ 450h ;"GetCalc("
hDelVar			equ 452h ;"DelVar "
hEquToStrng		equ 454h ;"Equ",Lconvert,"String("
hStrngToEqu		equ 456h ;"String",Lconvert,"Equ("
hDelLast		equ 458h ;"Clear Entries"
hSelect			equ 45Ah ;"Select("
hANOVA			equ 45Ch ;"ANOVA("
hModBox			equ 45Eh ;"ModBoxplot"
hNormProb		equ 460h ;"NormProbPlot"
hUnused03		equ 462h ;Can interfere with edit buffer navigation
hUnused04		equ 464h ;Can interfere with edit buffer navigation
hUnused05		equ 466h ;Can interfere with edit buffer navigation
hUnused06		equ 468h
hUnused07		equ 46Ah ;Can interfere with edit buffer navigation
hUnused08		equ 46Ch ;Can interfere with edit buffer navigation
hUnused09		equ 46Eh ;Can interfere with edit buffer navigation
hUnused10		equ 470h ;Can interfere with edit buffer navigation
hMGT			equ 472h ;"G-T"
hZFit			equ 474h ;"ZoomFit"
hDiag_on		equ 476h ;"DiagnosticOn"
hDiag_off		equ 478h ;"DiagnosticOff"
hOkEnd2v0		equ 478h
hArchive		equ 47Ah ;"Archive "
hUnarchive		equ 47Ch ;"UnArchive "
hasm			equ 47Eh ;"Asm("
hasmComp		equ 480h ;"AsmComp("
hasmPrgm		equ 482h ;"AsmPrgm"
hasmCmp			equ 484h
hLcapAAcute		equ 486h ;LcapAAcute
hLcapAGrave		equ 488h ;LcapAGrave
hLcapACaret		equ 48Ah ;LcapACaret
hLcapADier		equ 48Ch ;LcapADier
hLaAcute		equ 48Eh ;LaAcute
hLaGrave		equ 490h ;LaGrave
hLaCaret		equ 492h ;LaCaret
hLaDier			equ 494h ;LaDier
hLcapEAcute		equ 496h ;LcapEAcute
hLcapEGrave		equ 498h ;LcapEGrave
hLcapECaret		equ 49Ah ;LcapECaret
hLcapEDier		equ 49Ch ;LcapEDier
hLeAcute		equ 49Eh ;LeAcute
hLeGrave		equ 4A0h ;LeGrave
hLeCaret		equ 4A2h ;LeCaret
hLeDier			equ 4A4h ;LeDier
hUnused11		equ 4A6h ;Can interfere with edit buffer navigation
hLcapIGrave		equ 4A8h ;LcapIGrave
hLcapICaret		equ 4AAh ;LcapICaret
hLcapIDier		equ 4ACh ;LcapIDier
hLiAcute		equ 4AEh ;LiAcute
hLiGrave		equ 4B0h ;LiGrave
hLiCaret		equ 4B2h ;LiCaret
hLiDier			equ 4B4h ;LiDier
hLcapOAcute		equ 4B6h ;LcapOAcute
hLcapOGrave		equ 4B8h ;LcapOGrave
hLcapOCaret		equ 4BAh ;LcapOCaret
hLcapODier		equ 4BCh ;LcapODier
hLoAcute		equ 4BEh ;LoAcute
hLoGrave		equ 4C0h ;LoGrave
hLoCaret		equ 4C2h ;LoCaret
hLoDier			equ 4C4h ;LoDier
hLcapUAcute		equ 4C6h ;LcapUAcute
hLcapUGrave		equ 4C8h ;LcapUGrave
hLcapUCaret		equ 4CAh ;LcapUCaret
hLcapUDier		equ 4CCh ;LcapUDier
hLuAcute		equ 4CEh ;LuAcute
hLuGrave		equ 4D0h ;LuGrave
hLuCaret		equ 4D2h ;LuCaret
hLuDier			equ 4D4h ;LuDier
hLcapCCed		equ 4D6h ;LcapCCed
hLcCed			equ 4D8h ;LcCed
hLcapNTilde		equ 4DAh ;LcapNTilde
hLnTilde		equ 4DCh ;LnTilde
hLaccent		equ 4DEh ;Laccent
hLgrave			equ 4E0h ;Lgrave
hLdieresis		equ 4E2h ;Ldieresis
hLquesDown		equ 4E4h ;LquesDown
hLexclamDown		equ 4E6h ;LexclamDown
hLalpha			equ 4E8h ;Lalpha
hLbeta			equ 4EAh ;Lbeta
hLgamma			equ 4ECh ;Lgamma
hLcapDelta		equ 4EEh ;LcapDelta
hLdelta			equ 4F0h ;Ldelta
hLepsilon		equ 4F2h ;Lepsilon
hLlambda		equ 4F4h ;Llambda
hLmu			equ 4F6h ;Lmu
hLpi			equ 4F8h ;Lpi
hLrho			equ 4FAh ;Lrho
hLcapSigma		equ 4FCh ;LcapSigma
hUnused12		equ 4FEh ;Can interfere with edit buffer navigation
hLphi			equ 500h ;Lsigma
hLcapOmega		equ 502h ;LcapOmega
hLphat			equ 504h ;Lphat
hLchi			equ 506h ;Lchi
hLstatF			equ 508h ;LstatF
hLa			equ 50Ah ;"a"
hLb			equ 50Ch ;"b"
hLc			equ 50Eh ;"c"
hLd			equ 510h ;"d"
hLsmalle		equ 512h ;"e"
hLf			equ 514h ;"f"
hLsmallg		equ 516h ;"g"
hLh			equ 518h ;"h"
hLi			equ 51Ah ;"i"
hLj			equ 51Ch ;"j"
hLk			equ 51Eh ;"k"
hUnused13		equ 520h ;Can interfere with edit buffer navigation
hLl			equ 522h ;"l"
hLm			equ 524h ;"m"
hLsmalln		equ 526h ;"n"
hLo			equ 528h ;"o"
hLp			equ 52Ah ;"p"
hLq			equ 52Ch ;"q"
hLsmallr		equ 52Eh ;"r"
hLs			equ 530h ;"s"
hLsmallt		equ 532h ;"t"
hLu			equ 534h ;"u"
hLv			equ 536h ;"v"
hLw			equ 538h ;"w"
hLx			equ 53Ah ;"x"
hLy			equ 53Ch ;"y"
hLz			equ 53Eh ;"z"
hLsigma			equ 540h ;Lsigma
hLtau			equ 542h ;Ltau
hLcapIAcute		equ 544h ;LcapIAcute
hGarbagec		equ 546h ;"GarbageCollect"

;All Following Values Are Passed In BC With DE=hExtend

hExtend			equ 00Ch

;Added In OS Version 1.1.5

hTilde			equ 548h ;Ltilde
hAPos2			equ 54Ah ;Lapostrophe

;Added In OS Version 1.1.6

hAtSign			equ 54Ch ;LatSign
hPound			equ 54Eh ;Lpound
hDollarSign		equ 550h ;F2h
hAmpersand		equ 552h ;"&"
hBackquote		equ 554h ;"`"
hSemicolon		equ 556h ;";"
hBackslash		equ 558h ;"\"
hBar			equ 55Ah ;"|"
hUnderscore		equ 55Ch ;"_"
hPercent		equ 55Eh ;"%"
hEllipsis		equ 560h ;Lellipsis
hAngleSymbol		equ 562h ;Langle
hSharpS			equ 564h ;F4h
hSupX			equ 566h ;LsupX
hSubT			equ 568h ;LsubT
hSub0			equ 56Ah ;Lsub0
hSub1			equ 56Ch ;Lsub1
hSub2			equ 56Eh ;Lsub2
hSub3			equ 570h ;Lsub3
hSub4			equ 572h ;Lsub4
hSub5			equ 574h ;Lsub5
hSub6			equ 576h ;Lsub6
hSub7			equ 578h ;Lsub7
hSub8			equ 57Ah ;Lsub8
hSub9			equ 57Ch ;Lsub9
hTen			equ 57Eh ;Lten
hLeft			equ 580h ;Lleft
hConvert		equ 582h ;Lconvert
hUpArrow		equ 584h ;LupArrow
hDownArrow		equ 586h ;LdownArrow
hUnused14		equ 588h ;Can interfere with edit buffer navigation
hCross			equ 58Ah ;Lcross
hIntegral		equ 58Ch ;Lintegral
hSqUp			equ 58Eh ;LsqUp
hSqDown			equ 590h ;LsqDown
hRootSymbol		equ 592h ;Lroot
hInvEQ			equ 594h ;LinvEQ

;2nd Half Of 84-Plus Only Tokens
;-----------------------------------------------
hSetDate		equ 596h ;"setDate("
hSetTime		equ 598h ;"setTime("
hCheckTmr		equ 59Ah ;"checkTmr("
hSetDtFmt		equ 59Ch ;"setDtFmt("
hSetTmFmt		equ 59Eh ;"setTmFmt("
hTimeCnv		equ 5A0h ;"timeCnv("
hDayOfWk		equ 5A2h ;"dayOfWk("
hGetDtStr		equ 5A4h ;"getDtStr("
hGetTmStr		equ 5A6h ;"getTmStr("
hGetDate		equ 5A8h ;"getDate("
hGetTime		equ 5AAh ;"getTime("
hStartTmr		equ 5ACh ;"startTmr"
hGetDtFmt		equ 5AEh ;"getDtFmt"
hGetTmFmt		equ 5B0h ;"getTmFmt"
hIsClockOn		equ 5B2h ;"isClockOn"
hClockOff		equ 5B4h ;"ClockOff"
hClockOn		equ 5B6h ;"ClockOn"
hOpenLib		equ 5B8h ;"OpenLib("
hExecLib		equ 5BAh ;"ExecLib"

;Added In OS Version 2.30

hInvT			equ 5BCh ;"invT("
hChiGOFTest		equ 5BEh ;Lchi,Lsquare,"GOF-Test("
hLinRegTInt		equ 5C0h ;"LinRegTInt "
hManualFit		equ 5C2h ;"Manual-Fit "

;Added In OS Version 2.53

hZoomQ1			equ 5C4h ;"ZQuadrant1"
hZoom1_2		equ 5C6h ;"ZFrac1",F6h,"2"
hZoom1_3		equ 5C8h ;"ZFrac1",F6h,"3"
hZoom1_4		equ 5CAh ;"ZFrac1",F6h,"4"
hZoom1_5		equ 5CCh ;"ZFrac1",F6h,"5"
hZoom1_8		equ 5CEh ;"ZFrac1",F6h,"8"
hZoom1_10		equ 5D0h ;"ZFrac1",F6h,"10"
hEntryBox		equ 5D2h ;F7h
hUnused15		equ 5D4h
hUnused16		equ 5D6h
hUnused17		equ 5D8h
hUnused18		equ 5DAh
hUnused19		equ 5DCh
hUnused20		equ 5DEh
hUnused21		equ 5E0h
hUnused22		equ 5E2h
hUnused23		equ 5E4h
hUnused24		equ 5E6h
hUnused25		equ 5E8h
hUnused26		equ 5EAh
hUnused27		equ 5ECh
hUnused28		equ 5EEh
hUnused29		equ 5F0h
hOver			equ 5F2h ;F6h
hMix			equ 5F4h ;F5h
hToggleMixed		equ 5F6h ;Lconvert,"n",F6h,"d",Lleft,Lconvert,"Un",F6h,"d"
hToggleDec		equ 5F8h ;Lconvert,"F",Lleft,Lconvert,"D"
hRemainder		equ 5FAh ;"remainder("
hSummation		equ 5FCh ;LcapSigma,"("
hLogBase		equ 5FEh ;"logBASE("
hRandIntNoRep		equ 600h ;randIntNoRep("
hUnused30		equ 602h
hMathprint		equ 604h ;"MATHPRINT"
hClassic		equ 606h ;"CLASSIC"
hnOverd			equ 608h ;"n",F6h,"d"
hUnOverd		equ 60Ah ;"Un",F6h,"d"
hAuto			equ 60Ch ;"AUTO"
hDec			equ 60Eh ;"DEC"
hFrac			equ 610h ;"FRAC"
hUnused31		equ 612h

;Added In OS Version 2.55

hSTATWIZARDON		equ 614h ;"STATWIZARD ON"
hSTATWIZARDOFF		equ 616h ;"STATWIZARD OFF"
hUnused32		equ 618h
hUnused33		equ 61Ah