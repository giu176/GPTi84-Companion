# Axe native calculator app

## Why replace the BASIC bridge

The TI-BASIC `GPTI84` prototype proved the phone and Pico protocol, but the
calculator experience depends on `Pause`, `Str1`, `Str3..Str0`, and real `N`.
That leaves the program parked at `WAIT PHONE / THEN ENTER`, and missed or early
transfers can drop back to `Done`.

The production calculator UI is now an Axe program. Axe compiles to a no-stub
TI-83+/84+ executable, gives us a native key loop, direct screen control, and
direct link-port byte I/O without writing the whole application in pure Z80.

## Build workflow

1. Send `docs/axe/Axe.8xk` to the emulator or calculator with TI Connect.
2. Transfer `programs/axe_gpti84/AXGPTI84.8xp` to the calculator.
3. Compile `AXGPTI84` inside the Axe Parser app as a no-stub executable.
4. Run the compiled `prgmGPTI84`.

The repo does not contain a PC Axe compiler. The source program is generated as
a transfer-ready `.8xp`; the final executable is still produced by Axe Parser
on calculator/emulator.

## Current GUI-only behavior

- Launches directly into a native graph-buffer UI.
- Uses `Fix 5`, `ClrDraw`, `Line(`, pixel-positioned `Text(`, and
  `DispGraph`; the old home-screen `Output(`/`Pause` UI is no longer the app
  path.
- Does not talk to the Pico in this cut. Home renders a generated app-like
  list directly, and chat uses generated local 26x8 rows so the Wabbitemu UX
  can be tested without link-port noise.
- Runs as a state machine with three screens: `HOME`, `CHAT`, and `PROMPT`.
- Redraws a complete graph-buffer screen, then waits for a real key press before
  handling navigation. This follows the stable AlphaCS navigation pattern and
  avoids continuous redraw/link retry loops.
- Uses up/down on `HOME` to scroll through `NEW CHAT` plus 20 generated mock
  chats named `CHAT001`, `CHAT002`, and so on.
- Uses up/down inside `CHAT` to change pages. Left remains back navigation, and
  right remains prompt/send navigation.
- Creating a new chat opens the prompt screen first. Sending the prompt creates
  a generated `NEWxxx` row at the top of the chat list and opens that chat.
- Uses right on `HOME` to open the selected local placeholder chat.
- Uses up/down inside `CHAT` to page through the local placeholder rows.
- Removes the old chat footer. Chat row 1 reserves the last 9 characters for
  the page counter, such as `0001/0101`, leaving the rest of the row for the
  generated chat title with no separator dash.
- Uses real mock page totals: new chats have one page, most mock chats have a
  short page count, and `CHAT003` has 101 Shakespeare-text pages for scroll
  testing.
- Keeps the Axe source compact enough for on-calculator Axe Parser. Full
  dynamic wrapping is a Pico/phone rendering responsibility in the next cut;
  the calculator renders already-wrapped rows.
- Keeps key instructions out of the calculator GUI; controls are documented
  here instead of rendered as chat text.
- Uses right inside `CHAT` to open the prompt screen.
- Sent prompt choices appear as the first body row in the chat.
- Uses left as back navigation: `PROMPT -> CHAT -> HOME -> exit`.
- Keeps `ON` and `DEL` out of navigation; `DEL` remains reserved for a real text
  editor.
- Provides a minimal prompt path with selectable test prompts. Sending marks
  the chat with a UI-only status line; it does not persist anything yet.

The current `.8xp` is still a compact Axe source artifact that must be compiled
inside Axe Parser. It is not a finished standalone PC build output.

## Next Pico-mock cut

After emulator UX testing, remove the local placeholder chat rows and restore
the Pico-owned data path:

- transmit raw request frames with `Send(`;
- receive and validate response frames with `Get`;
- draw the first returned 16x8 `pages:N` page from the Pico mock;
- send `UP`/`DOWN` for Pico-owned chat scrolling;
- send `SEND:ACTIVE:<prompt>` from the prompt screen.

## Emulator/device test loop

1. Run the Axe executable on emulator or calculator without the Pico connected.
2. Confirm the UI stays open and does not return to `Done`.
3. Move the home selection with up/down keys.
4. Scroll past the first seven home rows and confirm all 20 mock chats are
   reachable.
5. Open `NEW CHAT`, choose a prompt, send it, and confirm a new `NEWxxx` chat
   opens with the prompt visible.
6. Return home and confirm each new `NEWxxx` entry appears at the top of the
   list.
7. Open local placeholder chats with right.
8. Open `CHAT003`, use up/down, and confirm it scrolls through 101 pages with
   four-digit page numbers.
9. Press right inside a chat, choose a prompt with up/down, then press right to
   return with `SENT UI ONLY` visible.
10. Press left and confirm navigation returns one level at a time.
