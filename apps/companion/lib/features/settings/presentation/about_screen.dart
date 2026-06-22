import 'package:flutter/material.dart';

class AboutScreen extends StatelessWidget {
  const AboutScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('About GPTi84 Companion')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 40),
        children: const [
          _InfoCard(
            icon: Icons.attach_file,
            title: 'Files and pictures',
            text:
                'Attachments are copied to app-private storage. OpenAI and Gemini accept supported images and documents; Anthropic accepts images and PDFs; compatible APIs and Ollama accept images when the model supports vision.',
          ),
          _InfoCard(
            icon: Icons.security_outlined,
            title: 'Credential security',
            text:
                'API keys and subscription tokens use Android Keystore or iOS Keychain and are never written to the chat database or sent to the calculator.',
          ),
          _InfoCard(
            icon: Icons.receipt_long_outlined,
            title: 'API billing',
            text:
                'API usage is billed by its provider. Consumer ChatGPT, Claude, or Gemini subscriptions do not automatically include third-party API credits.',
          ),
          _InfoCard(
            icon: Icons.privacy_tip_outlined,
            title: 'Local-first privacy',
            text:
                'Complete chat history remains in app-private storage. Only messages and attachments included in a request are shared with the selected provider.',
          ),
        ],
      ),
    );
  }
}

class _InfoCard extends StatelessWidget {
  const _InfoCard({
    required this.icon,
    required this.title,
    required this.text,
  });

  final IconData icon;
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            CircleAvatar(child: Icon(icon)),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: Theme.of(context).textTheme.titleMedium),
                  const SizedBox(height: 6),
                  Text(text),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
