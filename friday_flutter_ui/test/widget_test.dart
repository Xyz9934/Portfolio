import 'package:flutter_test/flutter_test.dart';

import 'package:friday_flutter_ui/main.dart';

void main() {
  testWidgets('renders FRIDAY shell', (tester) async {
    await tester.pumpWidget(const FridayApp());

    expect(find.text('FRIDAY'), findsOneWidget);
    expect(find.text('Recent Conversations'), findsOneWidget);
    expect(find.text('Tap to speak'), findsOneWidget);
  });
}
