# Axe GPTi84 calculator app

`AXGPTI84.basic` is the transfer-ready Axe source program. Compile it inside
Axe Parser on a TI-84 Plus monochrome emulator or calculator. `GPTI84_AXE.axe`
is the readable design note for the same app.

Workflow:

1. Send `docs/axe/Axe.8xk` to the emulator/calculator.
2. Send `programs/axe_gpti84/AXGPTI84.8xp` to the calculator.
3. Open Axe Parser and compile `AXGPTI84` to a no-stub executable.
4. Run the compiled `prgmGPTI84`.

The current build is a GUI-only emulator prototype. It proves the native
graph-buffer UI, deterministic arrow-key loop, home/chat/prompt navigation,
scrolling catalog behavior, and prompt-selection flow without trying to talk to
the Pico. Home renders a generated app-like list directly, and chat draws from
a generated 26x8 row buffer so the next version can replace the local generator
with Pico-provided rows.

Implemented keys:

- Up/down: move through the 20-chat mock catalog (`CHAT001`, `CHAT002`, ...),
  page the active placeholder chat, and choose one of the canned prompt texts.
- Left stays reserved for back navigation. Right stays reserved for opening the
  prompt screen or sending the selected prompt.
- Right on `NEW CHAT`: open the prompt screen. Sending creates a generated
  `NEWxxx` mock chat, pushes it to the top of the catalog, and opens it with
  the selected prompt visible.
- Right on a chat: open the selected local placeholder chat.
- Right in chat: open prompt screen.
- Right in prompt: mark a UI-only send and return to the chat.
- Left: back one level; exits only from home.

Chat headers use the compact row shape planned for Pico pages:
the generated title uses the left side of the row, while the final 9 characters
hold four-digit current/total page numbers such as `0001/0101`, with no dash
separator. `CHAT003` is a 101-page Shakespeare-text scroll test; most other
mock chats use a short real page count. Key instructions are intentionally not
rendered inside the calculator GUI.

The Axe source is intentionally compact for on-calculator Axe Parser. Full
dynamic wrapping should happen in the Pico/phone renderer before rows are sent
to the calculator.

The next cut should replace the local row generator, restore raw framed
`LIST`, `OPEN:<slot>`, `NEW`, `UP`, `DOWN`, and `SEND:ACTIVE:<prompt>`
requests, and draw 16x8 `pages:N` rows supplied by `src/raw_axe_mock.py`.
