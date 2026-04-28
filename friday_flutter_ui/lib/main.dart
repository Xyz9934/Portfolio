import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() {
  runApp(const FridayApp());
}

class FridayApp extends StatelessWidget {
  const FridayApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'FRIDAY',
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF070B16),
        useMaterial3: true,
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF6B5DFF),
          secondary: Color(0xFF22D3EE),
          surface: Color(0xFF10182B),
        ),
      ),
      home: const FridayShell(),
    );
  }
}

class FridayShell extends StatefulWidget {
  const FridayShell({super.key});

  @override
  State<FridayShell> createState() => _FridayShellState();
}

class _FridayShellState extends State<FridayShell> {
  int _currentIndex = 0;
  String? _pendingPrompt;

  late final FridayApiClient _apiClient = FridayApiClient();

  @override
  Widget build(BuildContext context) {
    final screens = [
      HomeScreen(
        apiBaseUrl: _apiClient.baseUrl,
        onOpenChat: () => setState(() => _currentIndex = 1),
        onAskPrompt: (prompt) => setState(() {
          _pendingPrompt = prompt;
          _currentIndex = 1;
        }),
      ),
      ChatScreen(
        apiClient: _apiClient,
        initialPrompt: _pendingPrompt,
        onPromptConsumed: () => _pendingPrompt = null,
      ),
      const ToolsScreen(),
      SettingsScreen(apiBaseUrl: _apiClient.baseUrl),
      ProfileScreen(apiBaseUrl: _apiClient.baseUrl),
    ];

    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF0A1020), Color(0xFF05070D)],
          ),
        ),
        child: SafeArea(child: screens[_currentIndex]),
      ),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 0, 18, 18),
          child: Container(
            height: 74,
            decoration: BoxDecoration(
              color: const Color(0xCC0D1323),
              borderRadius: BorderRadius.circular(26),
              border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
              boxShadow: const [
                BoxShadow(
                  color: Color(0x66000000),
                  blurRadius: 24,
                  offset: Offset(0, 14),
                ),
              ],
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: List.generate(_navItems.length, (index) {
                final item = _navItems[index];
                final selected = _currentIndex == index;
                return GestureDetector(
                  onTap: () => setState(() => _currentIndex = index),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 220),
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      shape: index == 2 ? BoxShape.circle : BoxShape.rectangle,
                      borderRadius: index == 2 ? null : BorderRadius.circular(20),
                      gradient: selected
                          ? const LinearGradient(
                              colors: [Color(0xFF4B68FF), Color(0xFF7A43FF)],
                            )
                          : null,
                    ),
                    child: Icon(
                      item.icon,
                      color: selected ? Colors.white : const Color(0xFF8590AF),
                      size: index == 2 ? 28 : 22,
                    ),
                  ),
                );
              }),
            ),
          ),
        ),
      ),
    );
  }
}

class FridayApiClient {
  FridayApiClient({http.Client? httpClient})
      : _httpClient = httpClient ?? http.Client(),
        baseUrl = _resolveBaseUrl();

  final http.Client _httpClient;
  final String baseUrl;

  static String _resolveBaseUrl() {
    const configured = String.fromEnvironment('FRIDAY_API_BASE_URL');
    if (configured.isNotEmpty) {
      return configured;
    }
    if (kIsWeb) {
      return 'http://localhost:5000';
    }
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:5000';
    }
    return 'http://127.0.0.1:5000';
  }

  Future<String> askQuestion(String question) async {
    final response = await _httpClient.post(
      Uri.parse('$baseUrl/ask'),
      headers: const {'Content-Type': 'application/json'},
      body: jsonEncode({'question': question}),
    );

    final payload = jsonDecode(response.body) as Map<String, dynamic>;
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return (payload['answer'] ?? '').toString().trim();
    }

    final message = (payload['error'] ?? 'Unknown error').toString();
    throw Exception(message);
  }

  Future<bool> checkHealth() async {
    try {
      final response = await _httpClient
          .get(Uri.parse('$baseUrl/health'))
          .timeout(const Duration(seconds: 4));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}

class HomeScreen extends StatelessWidget {
  const HomeScreen({
    required this.apiBaseUrl,
    required this.onOpenChat,
    required this.onAskPrompt,
    super.key,
  });

  final String apiBaseUrl;
  final VoidCallback onOpenChat;
  final ValueChanged<String> onAskPrompt;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const TopBar(),
          const SizedBox(height: 26),
          RichText(
            text: const TextSpan(
              style: TextStyle(
                fontSize: 30,
                fontWeight: FontWeight.w700,
                color: Colors.white,
              ),
              children: [
                TextSpan(text: 'Good Evening, '),
                TextSpan(
                  text: 'Alex',
                  style: TextStyle(color: Color(0xFF77A2FF)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          const Text(
            'How can I assist you today?',
            style: TextStyle(color: Color(0xFF8D98B8), fontSize: 15),
          ),
          const SizedBox(height: 28),
          GestureDetector(
            onTap: onOpenChat,
            child: const Center(child: VoiceOrb()),
          ),
          const SizedBox(height: 18),
          Center(
            child: Text(
              'Backend: $apiBaseUrl',
              style: const TextStyle(color: Color(0xFF67728F), fontSize: 12),
            ),
          ),
          const SizedBox(height: 30),
          Row(
            children: [
              Expanded(
                child: ActionCard(
                  icon: Icons.flash_on_rounded,
                  title: 'Quick',
                  subtitle: 'Fast answers to simple questions',
                  onTap: () => onAskPrompt('Give me a quick summary of today\'s priorities.'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ActionCard(
                  icon: Icons.psychology_alt_rounded,
                  title: 'Deep',
                  subtitle: 'Detailed analysis and insights',
                  onTap: () => onAskPrompt('Analyze this problem step by step.'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: ActionCard(
                  icon: Icons.shield_rounded,
                  title: 'Safe',
                  subtitle: 'Filtered and secure responses',
                  onTap: () => onAskPrompt('Answer carefully and keep the response safe.'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 28),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: const [
              Text(
                'Recent Conversations',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
              ),
              Text(
                'View all',
                style: TextStyle(
                  color: Color(0xFF7B87FF),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          ..._recentChats.map(
            (chat) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ConversationTile(
                icon: chat.icon,
                title: chat.title,
                meta: chat.meta,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({
    required this.apiClient,
    this.initialPrompt,
    this.onPromptConsumed,
    super.key,
  });

  final FridayApiClient apiClient;
  final String? initialPrompt;
  final VoidCallback? onPromptConsumed;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();

  late List<ChatMessage> _messages = [
    const ChatMessage(
      text: 'Hello. I am FRIDAY, connected to your local assistant backend.',
      isUser: false,
    ),
  ];

  bool _isSending = false;
  bool _backendOnline = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    unawaited(_checkBackend());
    _sendPendingPrompt();
  }

  @override
  void didUpdateWidget(covariant ChatScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.initialPrompt != oldWidget.initialPrompt) {
      _sendPendingPrompt();
    }
  }

  void _sendPendingPrompt() {
    final prompt = widget.initialPrompt?.trim();
    if (prompt == null || prompt.isEmpty) {
      return;
    }
    widget.onPromptConsumed?.call();
    unawaited(_sendMessage(prompt));
  }

  Future<void> _checkBackend() async {
    final online = await widget.apiClient.checkHealth();
    if (!mounted) {
      return;
    }
    setState(() {
      _backendOnline = online;
    });
  }

  Future<void> _sendMessage([String? prompt]) async {
    final text = (prompt ?? _controller.text).trim();
    if (text.isEmpty || _isSending) {
      return;
    }

    _controller.clear();
    setState(() {
      _errorMessage = null;
      _isSending = true;
      _messages = [
        ..._messages,
        ChatMessage(text: text, isUser: true),
      ];
    });
    _scrollToBottom();

    try {
      final answer = await widget.apiClient.askQuestion(text);
      if (!mounted) {
        return;
      }
      setState(() {
        _backendOnline = true;
        _messages = [
          ..._messages,
          ChatMessage(
            text: answer.isEmpty ? 'FRIDAY returned an empty response.' : answer,
            isUser: false,
          ),
        ];
      });
    } catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _backendOnline = false;
        _errorMessage = error.toString().replaceFirst('Exception: ', '');
        _messages = [
          ..._messages,
          const ChatMessage(
            text: 'I could not reach the FRIDAY backend. Start server.py and try again.',
            isUser: false,
            isError: true,
          ),
        ];
      });
    } finally {
      if (mounted) {
        setState(() {
          _isSending = false;
        });
      }
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scrollController.hasClients) {
        return;
      }
      _scrollController.animateTo(
        _scrollController.position.maxScrollExtent + 120,
        duration: const Duration(milliseconds: 240),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 12, 20, 20),
      child: Column(
        children: [
          Row(
            children: [
              const CircleIcon(icon: Icons.bolt_rounded),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  children: [
                    const Text(
                      'Chat with FRIDAY',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _backendOnline ? 'backend online' : 'backend offline',
                      style: TextStyle(
                        color: _backendOnline ? const Color(0xFF57E6A8) : const Color(0xFFFF8E8E),
                        fontSize: 12,
                      ),
                    ),
                  ],
                ),
              ),
              GestureDetector(
                onTap: _checkBackend,
                child: const CircleAvatar(
                  radius: 18,
                  backgroundColor: Color(0xFF19233A),
                  child: Icon(Icons.refresh_rounded, color: Colors.white),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          if (_errorMessage != null)
            Container(
              width: double.infinity,
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF2A1420),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0x66FF5F87)),
              ),
              child: Text(
                _errorMessage!,
                style: const TextStyle(color: Color(0xFFFFC8D5)),
              ),
            ),
          Expanded(
            child: ListView.separated(
              controller: _scrollController,
              itemCount: _messages.length + 1,
              separatorBuilder: (_, __) => const SizedBox(height: 14),
              itemBuilder: (context, index) {
                if (index == _messages.length) {
                  return const ActionChipRow();
                }
                final message = _messages[index];
                return Align(
                  alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: ChatBubble(
                    text: message.text,
                    isUser: message.isUser,
                    isError: message.isError,
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFF0F1628),
              borderRadius: BorderRadius.circular(24),
              border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    minLines: 1,
                    maxLines: 4,
                    onSubmitted: (_) => _sendMessage(),
                    decoration: const InputDecoration(
                      border: InputBorder.none,
                      hintText: 'Type your message...',
                      hintStyle: TextStyle(color: Color(0xFF74809D)),
                    ),
                  ),
                ),
                if (_isSending)
                  const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  GestureDetector(
                    onTap: _sendMessage,
                    child: const CircleAvatar(
                      radius: 18,
                      backgroundColor: Color(0xFF6F63FF),
                      child: Icon(Icons.arrow_upward_rounded, size: 18),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class ToolsScreen extends StatelessWidget {
  const ToolsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Text(
            'FRIDAY Tools',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          ),
          SizedBox(height: 18),
          GridTools(),
        ],
      ),
    );
  }
}

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({required this.apiBaseUrl, super.key});

  final String apiBaseUrl;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'FRIDAY Control Panel',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 22),
          const SectionLabel('Response Style'),
          const SizedBox(height: 12),
          const SegmentedChoices(options: ['Default', 'Bullet Points', 'Explain Like I\'m 5'], selected: 0),
          const SizedBox(height: 20),
          const SectionLabel('Intelligence Level'),
          const SizedBox(height: 12),
          const SegmentedChoices(options: ['Quick', 'Smart', 'Deep'], selected: 1),
          const SizedBox(height: 20),
          const SectionLabel('Backend Endpoint'),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF12192A),
              borderRadius: BorderRadius.circular(18),
            ),
            child: Text(
              apiBaseUrl,
              style: const TextStyle(color: Color(0xFFD8DEF1)),
            ),
          ),
          const SizedBox(height: 20),
          const SectionLabel('Safety Filter'),
          const SizedBox(height: 8),
          Row(
            children: [
              const Expanded(
                child: Text(
                  'Enable safe format for all responses',
                  style: TextStyle(color: Color(0xFF8B95B2)),
                ),
              ),
              Switch(
                value: true,
                onChanged: (_) {},
                activeThumbColor: const Color(0xFF7861FF),
              ),
            ],
          ),
          const SizedBox(height: 20),
          const SectionLabel('Custom Instructions'),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF12192A),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Text(
              'Always explain with real-world examples.',
              style: TextStyle(color: Color(0xFFD8DEF1)),
            ),
          ),
          const SizedBox(height: 26),
          SizedBox(
            width: double.infinity,
            child: FilledButton(
              onPressed: () {},
              style: FilledButton.styleFrom(
                backgroundColor: const Color(0xFF7158FF),
                minimumSize: const Size.fromHeight(56),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
              ),
              child: const Text('Save Preferences'),
            ),
          ),
        ],
      ),
    );
  }
}

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({required this.apiBaseUrl, super.key});

  final String apiBaseUrl;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
      child: Column(
        children: [
          const SizedBox(height: 10),
          const MiniOrb(),
          const SizedBox(height: 18),
          const Text(
            'Alex',
            style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          const Text(
            'PRO USER',
            style: TextStyle(
              color: Color(0xFF8C97B6),
              letterSpacing: 1.6,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            apiBaseUrl,
            style: const TextStyle(color: Color(0xFF69748E), fontSize: 12),
          ),
          const SizedBox(height: 22),
          const Row(
            children: [
              Expanded(child: StatCard(value: '125', label: 'Requests')),
              SizedBox(width: 12),
              Expanded(child: StatCard(value: '48', label: 'Saved Chats')),
              SizedBox(width: 12),
              Expanded(child: StatCard(value: '12', label: 'Tools Used')),
            ],
          ),
          const SizedBox(height: 20),
          ..._profileOptions.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: ConversationTile(
                icon: item.icon,
                title: item.title,
                meta: item.meta,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class GridTools extends StatelessWidget {
  const GridTools({super.key});

  @override
  Widget build(BuildContext context) {
    return GridView.count(
      crossAxisCount: 2,
      childAspectRatio: 1.1,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisSpacing: 14,
      mainAxisSpacing: 14,
      children: const [
        ToolCard(icon: Icons.manage_search_rounded, title: 'Web Search', subtitle: 'Smart browsing'),
        ToolCard(icon: Icons.description_outlined, title: 'Summarizer', subtitle: 'Condense text fast'),
        ToolCard(icon: Icons.image_search_rounded, title: 'Vision', subtitle: 'Image analysis'),
        ToolCard(icon: Icons.code_rounded, title: 'Code Assistant', subtitle: 'Write and explain'),
        ToolCard(icon: Icons.brush_rounded, title: 'Image Creator', subtitle: 'Generate visuals'),
        ToolCard(icon: Icons.bar_chart_rounded, title: 'Data Analyst', subtitle: 'Charts and insights'),
      ],
    );
  }
}

class TopBar extends StatelessWidget {
  const TopBar({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        const CircleIcon(icon: Icons.menu_rounded),
        const SizedBox(width: 12),
        Expanded(
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: const LinearGradient(
                    colors: [Color(0xFF4E7CFF), Color(0xFF7D42FF)],
                  ),
                  boxShadow: const [
                    BoxShadow(
                      color: Color(0x665F6BFF),
                      blurRadius: 18,
                      spreadRadius: 2,
                    ),
                  ],
                ),
                child: const Icon(Icons.auto_awesome, size: 16),
              ),
              const SizedBox(width: 10),
              const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'FRIDAY',
                    style: TextStyle(fontWeight: FontWeight.w700, letterSpacing: 2),
                  ),
                  Text(
                    'AI Assistant',
                    style: TextStyle(color: Color(0xFF7884A3), fontSize: 11),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(width: 12),
        const CircleIcon(icon: Icons.graphic_eq_rounded),
      ],
    );
  }
}

class VoiceOrb extends StatelessWidget {
  const VoiceOrb({super.key});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        SizedBox(
          width: 220,
          height: 220,
          child: CustomPaint(
            painter: OrbPainter(),
            child: Center(
              child: Icon(Icons.multitrack_audio_rounded, size: 48, color: Colors.white),
            ),
          ),
        ),
        SizedBox(height: 14),
        Text(
          'Tap to speak',
          style: TextStyle(color: Color(0xFF7985A6)),
        ),
      ],
    );
  }
}

class MiniOrb extends StatelessWidget {
  const MiniOrb({super.key});

  @override
  Widget build(BuildContext context) {
    return const SizedBox(
      width: 112,
      height: 112,
      child: CustomPaint(
        painter: OrbPainter(compact: true),
        child: Center(
          child: Icon(Icons.face_retouching_natural_rounded, color: Colors.white),
        ),
      ),
    );
  }
}

class OrbPainter extends CustomPainter {
  const OrbPainter({this.compact = false});

  final bool compact;

  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero);
    final radius = math.min(size.width, size.height) / 2;
    final glowRect = Rect.fromCircle(center: center, radius: radius);

    final glowPaint = Paint()
      ..shader = const RadialGradient(
        colors: [
          Color(0xAA3A7BFF),
          Color(0x88335BFF),
          Color(0x11101A2F),
        ],
      ).createShader(glowRect);

    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = compact ? 3 : 4;

    canvas.drawCircle(center, radius, glowPaint);

    ringPaint.shader = const SweepGradient(
      colors: [Color(0xFF66D9FF), Color(0xFF7A4DFF), Color(0xFF66D9FF)],
    ).createShader(glowRect);
    canvas.drawCircle(center, radius * 0.72, ringPaint);

    ringPaint
      ..shader = null
      ..color = const Color(0x554E7CFF)
      ..strokeWidth = compact ? 2 : 3;
    canvas.drawCircle(center, radius * 0.87, ringPaint);

    final wavePaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = compact ? 3 : 4
      ..strokeCap = StrokeCap.round
      ..color = Colors.white;

    final path = Path();
    final width = radius * 0.92;
    for (var i = 0; i <= 48; i++) {
      final progress = i / 48;
      final x = center.dx - width / 2 + width * progress;
      final y = center.dy + math.sin(progress * math.pi * 4) * (compact ? 5 : 8);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(path, wavePaint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class ActionCard extends StatelessWidget {
  const ActionCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    super.key,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: _glassDecoration(),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: const Color(0xFF7B88FF)),
            const SizedBox(height: 14),
            Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Text(
              subtitle,
              style: const TextStyle(fontSize: 11, color: Color(0xFF8B95B2), height: 1.4),
            ),
          ],
        ),
      ),
    );
  }
}

class ConversationTile extends StatelessWidget {
  const ConversationTile({
    required this.icon,
    required this.title,
    required this.meta,
    super.key,
  });

  final IconData icon;
  final String title;
  final String meta;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: _glassDecoration(),
      child: Row(
        children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(
              color: const Color(0xFF151F36),
              borderRadius: BorderRadius.circular(14),
            ),
            child: Icon(icon, color: const Color(0xFF7A85FF)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
                const SizedBox(height: 4),
                Text(meta, style: const TextStyle(color: Color(0xFF8C97B6), fontSize: 12)),
              ],
            ),
          ),
          const Icon(Icons.chevron_right_rounded, color: Color(0xFF6F7894)),
        ],
      ),
    );
  }
}

class ChatBubble extends StatelessWidget {
  const ChatBubble({
    required this.text,
    this.isUser = false,
    this.isError = false,
    super.key,
  });

  final String text;
  final bool isUser;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 290),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: isUser
            ? const LinearGradient(colors: [Color(0xFF273A7A), Color(0xFF5E4BFF)])
            : null,
        color: isUser
            ? null
            : isError
                ? const Color(0xFF291724)
                : const Color(0xFF111A2D),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: Text(
        text,
        style: const TextStyle(height: 1.55, color: Color(0xFFE3E9FB)),
      ),
    );
  }
}

class ActionChipRow extends StatelessWidget {
  const ActionChipRow({super.key});

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: const [
        PromptChip(label: 'Explain deeper'),
        PromptChip(label: 'Give example'),
        PromptChip(label: 'Make it simple'),
      ],
    );
  }
}

class PromptChip extends StatelessWidget {
  const PromptChip({required this.label, super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF121A2D),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 12, color: Color(0xFFB8C1DA)),
      ),
    );
  }
}

class ToolCard extends StatelessWidget {
  const ToolCard({
    required this.icon,
    required this.title,
    required this.subtitle,
    super.key,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: _glassDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              gradient: const LinearGradient(colors: [Color(0xFF223A79), Color(0xFF6B4CFF)]),
            ),
            child: Icon(icon, color: Colors.white),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text(
                subtitle,
                style: const TextStyle(color: Color(0xFF8A95B2), fontSize: 12),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class SectionLabel extends StatelessWidget {
  const SectionLabel(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      style: const TextStyle(
        color: Color(0xFFDCE4FB),
        fontSize: 16,
        fontWeight: FontWeight.w600,
      ),
    );
  }
}

class SegmentedChoices extends StatelessWidget {
  const SegmentedChoices({
    required this.options,
    required this.selected,
    super.key,
  });

  final List<String> options;
  final int selected;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF111A2E),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Row(
        children: List.generate(options.length, (index) {
          final isSelected = index == selected;
          return Expanded(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                gradient: isSelected
                    ? const LinearGradient(colors: [Color(0xFF4E6FFF), Color(0xFF7D42FF)])
                    : null,
              ),
              child: Text(
                options[index],
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 12,
                  color: isSelected ? Colors.white : const Color(0xFF8A95B2),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          );
        }),
      ),
    );
  }
}

class StatCard extends StatelessWidget {
  const StatCard({
    required this.value,
    required this.label,
    super.key,
  });

  final String value;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 18),
      decoration: _glassDecoration(),
      child: Column(
        children: [
          Text(
            value,
            style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 6),
          Text(
            label,
            style: const TextStyle(color: Color(0xFF8994B2), fontSize: 12),
          ),
        ],
      ),
    );
  }
}

class CircleIcon extends StatelessWidget {
  const CircleIcon({required this.icon, super.key});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(
        color: const Color(0xFF121A2D),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Icon(icon, color: Colors.white),
    );
  }
}

BoxDecoration _glassDecoration() {
  return BoxDecoration(
    color: const Color(0xCC121A2C),
    borderRadius: BorderRadius.circular(22),
    border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
    boxShadow: const [
      BoxShadow(
        color: Color(0x33000000),
        blurRadius: 26,
        offset: Offset(0, 14),
      ),
    ],
  );
}

class ChatMessage {
  const ChatMessage({
    required this.text,
    required this.isUser,
    this.isError = false,
  });

  final String text;
  final bool isUser;
  final bool isError;
}

class _NavItem {
  const _NavItem(this.icon);

  final IconData icon;
}

class _ConversationItem {
  const _ConversationItem(this.icon, this.title, this.meta);

  final IconData icon;
  final String title;
  final String meta;
}

const List<_NavItem> _navItems = [
  _NavItem(Icons.home_rounded),
  _NavItem(Icons.chat_bubble_rounded),
  _NavItem(Icons.auto_awesome_rounded),
  _NavItem(Icons.grid_view_rounded),
  _NavItem(Icons.person_rounded),
];

const List<_ConversationItem> _recentChats = [
  _ConversationItem(Icons.auto_awesome_rounded, 'Explain Quantum Computing', 'Friday • 2 min ago'),
  _ConversationItem(Icons.code_rounded, 'Write a Python Program', 'Friday • 15 min ago'),
  _ConversationItem(Icons.psychology_alt_rounded, 'How does AI work?', 'Friday • 1 hour ago'),
];

const List<_ConversationItem> _profileOptions = [
  _ConversationItem(Icons.verified_user_outlined, 'My Account', 'Manage your profile'),
  _ConversationItem(Icons.workspace_premium_outlined, 'Subscription', 'Pro Plan'),
  _ConversationItem(Icons.settings_suggest_outlined, 'Usage Stats', 'Export and history'),
  _ConversationItem(Icons.logout_rounded, 'Log Out', 'Leave this session'),
];
