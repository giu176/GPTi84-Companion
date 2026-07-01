import '../../conversations/data/app_database.dart';

const pinnedCatalogMagic = 'GPTI84PINS 1';
const fnv1a32Offset = 0x811c9dc5;
const fnv1a32Prime = 0x01000193;

class PinnedCatalogEntry {
  const PinnedCatalogEntry({
    required this.chatId,
    required this.revision,
    required this.hash,
    required this.title,
    required this.preview,
  });

  final String chatId;
  final int revision;
  final int hash;
  final String title;
  final String preview;
}

class PinnedCatalog {
  const PinnedCatalog({
    required this.deviceId,
    required this.revision,
    required this.hash,
    required this.entries,
  });

  final String deviceId;
  final int revision;
  final int hash;
  final List<PinnedCatalogEntry> entries;

  String encode() {
    final lines = <String>[
      pinnedCatalogMagic,
      'device=${escapeCatalogField(deviceId)}',
      'catalogRev=$revision',
      'catalogHash=${hash.toRadixString(16).padLeft(8, '0')}',
      for (final entry in entries)
        [
          'C',
          escapeCatalogField(entry.chatId),
          entry.revision.toString(),
          entry.hash.toRadixString(16).padLeft(8, '0'),
          escapeCatalogField(entry.title),
          escapeCatalogField(entry.preview),
        ].join('|'),
    ];
    return '${lines.join('\n')}\n';
  }

  static PinnedCatalog fromProjections({
    required String deviceId,
    required List<PinnedConversationProjection> projections,
  }) {
    final entries = [
      for (final projection in projections)
        PinnedCatalogEntry(
          chatId: projection.conversationId,
          revision: projection.revision,
          hash: hashCatalogEntry(
            chatId: projection.conversationId,
            revision: projection.revision,
            title: projection.title,
            preview: projection.text,
          ),
          title: projection.title,
          preview: projection.text,
        ),
    ];
    final revision = entries.fold<int>(
      0,
      (current, entry) => entry.revision > current ? entry.revision : current,
    );
    final hash = fnv1a32(
      [
        for (final entry in entries)
          '${entry.chatId}\u001f${entry.revision}\u001f${entry.hash}\n',
      ].join().codeUnits,
    );
    return PinnedCatalog(
      deviceId: deviceId,
      revision: revision,
      hash: hash,
      entries: entries,
    );
  }
}

int hashCatalogEntry({
  required String chatId,
  required int revision,
  required String title,
  required String preview,
}) {
  return fnv1a32('$chatId\u001f$revision\u001f$title\u001f$preview'.codeUnits);
}

int fnv1a32(Iterable<int> bytes) {
  var hash = fnv1a32Offset;
  for (final byte in bytes) {
    hash ^= byte & 0xff;
    hash = (hash * fnv1a32Prime) & 0xffffffff;
  }
  return hash;
}

String escapeCatalogField(String value) {
  final buffer = StringBuffer();
  for (final codeUnit in value.codeUnits) {
    final mustEscape = codeUnit < 0x20 || codeUnit == 0x25 || codeUnit == 0x7c;
    if (mustEscape) {
      buffer
        ..write('%')
        ..write(codeUnit.toRadixString(16).padLeft(2, '0').toUpperCase());
    } else {
      buffer.writeCharCode(codeUnit);
    }
  }
  return buffer.toString();
}

String unescapeCatalogField(String value) {
  final buffer = StringBuffer();
  for (var index = 0; index < value.length; index++) {
    final code = value.codeUnitAt(index);
    if (code == 0x25 && index + 2 < value.length) {
      final decoded = int.tryParse(
        value.substring(index + 1, index + 3),
        radix: 16,
      );
      if (decoded != null) {
        buffer.writeCharCode(decoded);
        index += 2;
        continue;
      }
    }
    buffer.writeCharCode(code);
  }
  return buffer.toString();
}
