# 363538434: DCHECK on V8 Parser while parsing Class Static Functions

## ClusterFuzz Report

```
Security Bug

Important: Please do not change the component of this bug manually.

Please READ THIS FAQ before filing a bug: https://chromium.googlesource.com/chromium/src/+/HEAD/docs/security/faq.md

Please see the following link for instructions on filing security bugs: https://www.chromium.org/Home/chromium-security/reporting-security-bugs

Reports may be eligible for reward payments under the Chrome VRP: https://g.co/chrome/vrp

NOTE: Security bugs are normally made public once a fix has been widely deployed.

-------------------------

## VULNERABILITY DETAILS
DCHECK on V8 Parser while parsing Class Static Functions.

### Stack Trace

```
#
# Fatal error in ../../src/parsing/parser.cc, line 1120
# Debug check failed: class_info.static_elements_function_id == initializer_id (3 vs. 2).
#
#
#
#FailureMessage Object: 0x7fff9480e098
==== C stack trace ===============================

    ./v8_12.8.374.24/v8/out/x64.debug/libv8_libbase.so(v8::base::debug::StackTrace::StackTrace()+0x1e) [0x7f657912917e]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8_libplatform.so(+0x5757d) [0x7f657908457d]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8_libbase.so(V8_Fatal(char const*, int, char const*, ...)+0x205) [0x7f65790fc675]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8_libbase.so(+0x5601c) [0x7f65790fc01c]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8_libbase.so(V8_Dcheck(char const*, int, char const*)+0x4d) [0x7f65790fc74d]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(v8::internal::Parser::ParseClassForMemberInitialization(v8::internal::FunctionKind, int, int, int, v8::internal::AstRawString const*)+0x41a) [0x7f6575b8dffa]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(v8::internal::Parser::ParseFunction(v8::internal::Isolate*, v8::internal::ParseInfo*, v8::internal::Handle<v8::internal::SharedFunctionInfo>)+0x6a2) [0x7f6575b8d802]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(v8::internal::parsing::ParseFunction(v8::internal::ParseInfo*, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Isolate*, v8::internal::parsing::ReportStatisticsMode)+0x362) [0x7f6575be22f2]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(v8::internal::parsing::ParseAny(v8::internal::ParseInfo*, v8::internal::Handle<v8::internal::SharedFunctionInfo>, v8::internal::Isolate*, v8::internal::parsing::ReportStatisticsMode)+0x1dc) [0x7f6575be254c]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(+0x6e71a0e) [0x7f6575071a0e]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(v8::internal::ErrorUtils::NewCalledNonCallableError(v8::internal::Isolate*, v8::internal::Handle<v8::internal::Object>)+0x7b) [0x7f657507291b]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(+0x7bbadd2) [0x7f6575dbadd2]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(v8::internal::Runtime_ThrowCalledNonCallable(int, unsigned long*, v8::internal::Isolate*)+0xf8) [0x7f6575dbaca8]
    ./v8_12.8.374.24/v8/out/x64.debug/libv8.so(+0x608133d) [0x7f657428133d]
```

### Reproduction Steps

1) Build 12.8.374.24 with Debug mode by adding `is_debug = true` into args.gn.
2) Execute the testcase attached: `./d8 reduced_dcheck_class_static_function.js`
3) It should print the DCheck mentioned on the Stack Trace.

### Root Cause

#### Initial considerations:

- The misaligment between `class_info.static_elements_function_id` and `initializer_id` triggers the DCheck which happens inside `ParseClassForMemberInitialization` function: `DCHECK_EQ(class_info.static_elements_function_id, initializer_id);`
- `ParseClassForMemberInitialization` receives the `initializer_id` by parameter. 
- `class_info.static_elements_function_id` gets the value of `function_literal_id_` which is a member of `parser-base.h`
- `function_literal_id_` can be manipulated by the functions: `GetNextFunctionLiteralId`, `SkipFunctionLiterals` and `ResetFunctionLiteralId`.

#### The problem:

```
FunctionLiteral* Parser::ParseClassForMemberInitialization(
    FunctionKind initalizer_kind, int initializer_pos, int initializer_id,
    int initializer_end_pos, const AstRawString* class_name) {
  
  ...
  ResetFunctionLiteralId(); //[1]
  SkipFunctionLiterals(initializer_id - 1); //[2]
  ...

    ParseClassLiteralBody(class_info, class_name, class_token_pos, Token::kEos); //[3]

    if (initalizer_kind == FunctionKind::kClassMembersInitializerFunction) {
     ...
    } else {
      DCHECK_EQ(class_info.static_elements_function_id, initializer_id); //[4]
      initializer = CreateStaticElementsInitializer(class_name, &class_info);
    }
    ...
  }

  ...
  DCHECK_EQ(initializer->function_literal_id(), initializer_id); //[5]
  ...
}
```

[1] and [2] are used to set an initial value to `function_literal_id_`. As can be observed, it sets the value of `initializer_id - 1`, assuming that `function_literal_id_` will be increased only once. The problem is that `ParseClassLiteralBody` ([3]) increases multiple times the `function_literal_id_` variable causing the misaligment.

#### Multiple Increases of `function_literal_id_`:

```
template <typename Impl>
typename ParserBase<Impl>::ClassLiteralPropertyT
ParserBase<Impl>::ParseClassPropertyDefinition(ClassInfo* class_info,
                                               ParsePropertyInfo* prop_info,
                                               bool has_extends) {
  ...
  if (name_token == Token::kStatic) {
    ...
    if (peek() == Token::kLeftParen) {
      ...
    } else if (peek() == Token::kAssign || peek() == Token::kSemicolon ||
               peek() == Token::kRightBrace) {
      ...
    } else {
      prop_info->is_static = true;
      name_expression = ParseProperty(prop_info); //[6]
    }
  } else {
    ...
  }

  switch (prop_info->kind) {
    case ParsePropertyKind::kAssign:
    case ParsePropertyKind::kClassField:
    case ParsePropertyKind::kShorthandOrClassField:
    case ParsePropertyKind::kNotSet: { 

      ...

      ExpressionT initializer = ParseMemberInitializer(
          class_info, property_beg_pos, prop_info->is_static); //[7]
      ...

      //[8]
```

[6] `ParseProperty` increases the `function_literal_id_` via `ParseFunctionLiteral` function. Full backtrace:

```
#0  0x00004f0e3d4d174b in v8::internal::ParserBase<v8::internal::Parser>::GetNextFunctionLiteralId (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:296
#1  0x00004f0e3d4c39b0 in v8::internal::Parser::ParseFunctionLiteral (this=0x7fff7da5ec50, function_name=0x559dcbee9108, function_name_location=..., function_name_validity=v8::internal::kFunctionNameValidityUnknown, kind=v8::internal::FunctionKind::kNormalFunction, 
    function_token_pos=0x18, function_syntax_kind=v8::internal::FunctionSyntaxKind::kAnonymousExpression, language_mode=v8::internal::LanguageMode::kStrict, arguments_for_wrapped_function=0x0) at ../../src/parsing/parser.cc:2733
#2  0x00004f0e3d4f6a83 in v8::internal::ParserBase<v8::internal::Parser>::ParseFunctionExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3960
#3  0x00004f0e3d4f54cd in v8::internal::ParserBase<v8::internal::Parser>::ParsePrimaryExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:2121
#4  0x00004f0e3d4f45a7 in v8::internal::ParserBase<v8::internal::Parser>::ParseMemberExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3987
#5  0x00004f0e3d4f4447 in v8::internal::ParserBase<v8::internal::Parser>::ParseLeftHandSideExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3709
#6  0x00004f0e3d4f32ba in v8::internal::ParserBase<v8::internal::Parser>::ParsePostfixExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3676
#7  0x00004f0e3d4f2bde in v8::internal::ParserBase<v8::internal::Parser>::ParseUnaryExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3666
#8  0x00004f0e3d4f24ac in v8::internal::ParserBase<v8::internal::Parser>::ParseBinaryExpression (this=0x7fff7da5ec50, prec=0x6) at ../../src/parsing/parser-base.h:3548
#9  0x00004f0e3d4f1dac in v8::internal::ParserBase<v8::internal::Parser>::ParseLogicalExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3318
#10 0x00004f0e3d4f07fa in v8::internal::ParserBase<v8::internal::Parser>::ParseConditionalExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3303
#11 0x00004f0e3d4f0316 in v8::internal::ParserBase<v8::internal::Parser>::ParseAssignmentExpressionCoverGrammar (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:3090
#12 0x00004f0e3d4d77e5 in v8::internal::ParserBase<v8::internal::Parser>::ParseAssignmentExpression (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:2229
#13 0x00004f0e3d5002e4 in v8::internal::ParserBase<v8::internal::Parser>::ParseProperty (this=0x7fff7da5ec50, prop_info=0x7fff7da5e700) at ../../src/parsing/parser-base.h:2486
```

[7] `ParseMemberInitializer` increases the `function_literal_id_` via `EnsureStaticElementsScope`. Full backtrace:
```
#0  0x00004f0e3d4d174b in v8::internal::ParserBase<v8::internal::Parser>::GetNextFunctionLiteralId (this=0x7fff7da5ec50) at ../../src/parsing/parser-base.h:296
#1  0x00004f0e3d5036f8 in v8::internal::ParserBase<v8::internal::Parser>::ClassInfo::EnsureStaticElementsScope (this=0x7fff7da5e7e0, parser=0x7fff7da5ec50, beg_pos=0x10) at ../../src/parsing/parser-base.h:623
#2  0x00004f0e3d504576 in v8::internal::ParserBase<v8::internal::Parser>::ParseMemberInitializer (this=0x7fff7da5ec50, class_info=0x7fff7da5e7e0, beg_pos=0x10, is_static=0x1) at ../../src/parsing/parser-base.h:2696
```

[8] At this moment, the mismatch is already set. The function returns until the DCheck is hit.

### Bisect: Introduced Commit

Commit: cca606336c6753a2ddcd425019c1be11f9ba6216

Title: [parser] Only reparse the relevant segments for class initializers

Review: https://chromium-review.googlesource.com/c/v8/v8/+/5676330

### Bisect: Introduced Major Chrome

Chrome Stable: 128.0.6613.84

## VERSION
Chrome Version: [128.0.6613.113] + [stable]
Operating System: [All]

## REPRODUCTION CASE
Attached: `reduced_dcheck_class_static_function.js`

## FOR CRASHES, PLEASE INCLUDE THE FOLLOWING ADDITIONAL INFORMATION
Type of crash: [Browser]

## CREDIT INFORMATION
Reporter credit: Tashita Software Security
```

## Vulnerability Description

Minimal PoC: 'new class { static [function(){}] = [].trigger_error(); }' — uses a function expression as a computed property key and initializes with a call to a nonexistent method, triggering a parse or runtime assertion in class static property handling.

## Capabilities

Triggers a parser DCHECK or runtime assertion during class static computed property parsing. No memory read/write.
