; SWTOR mouseover cast — Tool A
; Rule: ONE keypress = ONE left-click (targets the unit under the cursor) + ONE ability key. Nothing else.
; No rotations, no chaining, no conditionals, no auto-fire. Keep it that way.
;
; Requires AutoHotkey v2 (https://www.autohotkey.com). Run this file; a green "H" appears in the tray.
; Only active while the SWTOR window is focused.

#Requires AutoHotkey v2.0
#SingleInstance Force

; --- Tuning ---------------------------------------------------------------
; Delay between the targeting click and the ability key. Too low and the ability
; fires on the OLD target; too high and it feels laggy. Start at 60, tune live.
CLICK_TO_CAST_DELAY_MS := 60

; If SWTOR ignores the synthetic click/keypress, uncomment these two lines to use
; the slower, more "real" event-based input:
; SendMode "Event"
; SetKeyDelay 20, 20

; --- Core -------------------------------------------------------------------
MouseoverCast(abilityKey) {
    Click "Left"                    ; target whatever is under the cursor
    Sleep CLICK_TO_CAST_DELAY_MS
    Send abilityKey                 ; press the ability's SWTOR keybind
}

; --- Bindings (edit these) ----------------------------------------------------
; Left side  = the key you press.
; Right side = the key SWTOR has the ability bound to. Modifiers: ^ = Ctrl, + = Shift, ! = Alt.
; Examples:  "1"  "{F3}"  "^2" (Ctrl+2)  "+q" (Shift+Q)
#HotIf WinActive("ahk_exe swtor.exe")

F5::MouseoverCast("1")
F6::MouseoverCast("2")
F7::MouseoverCast("3")

#HotIf
