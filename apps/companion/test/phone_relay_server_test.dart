import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gpti84_companion/features/relay/data/calculator_relay.dart';

void main() {
  test('parses calculator prompt and math pair', () {
    final (prompt, math) = parseCalculatorPair('prompt:hello\nmath:2*X\n');

    expect(prompt, 'hello');
    expect(math, '2*X');
  });

  test('parses V2 calculator commands', () {
    expect(parseCalculatorCommandV2('LIST'), isA<ListChatsCommand>());

    final open = parseCalculatorCommandV2('OPEN CABC');
    expect(open, isA<OpenChatCommand>());
    expect((open as OpenChatCommand).chatId, 'CABC');

    final send = parseCalculatorCommandV2('SEND CABC M1\nhello there');
    expect(send, isA<SendPromptCommand>());
    expect((send as SendPromptCommand).chatId, 'CABC');
    expect(send.clientMessageId, 'M1');
    expect(send.prompt, 'hello there');
  });

  test('builds fixed 16x7 calculator pages', () {
    final pages = layoutCalculatorPages('alpha beta gamma\ndelta');

    expect(pages, hasLength(1));
    expect(pages.single, hasLength(112));
    expect(pages.single.substring(0, 16), 'alpha beta gamma');
    expect(pages.single.substring(16, 32), 'delta'.padRight(16));
  });

  test('pages frame preserves Pico-compatible header and body size', () {
    final frame = pagesFrame('hello');
    final text = ascii.decode(frame);

    expect(text.startsWith('pages:1\n'), isTrue);
    expect(frame.length, 'pages:1\n'.length + 112);
  });

  test('calculator text replaces non-ascii glyphs', () {
    expect(calculatorSafeText('A→B'), 'A B');
  });
}
