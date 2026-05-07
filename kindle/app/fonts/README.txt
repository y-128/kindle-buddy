Place Japanese-capable fonts here before deploying to the Kindle.

Recommended:

  NotoSansCJKjp-Regular.otf
  NotoSansMonoCJKjp-Regular.otf   # optional; sans is used as fallback
  LICENSE-NotoSansCJK.txt

The renderer also recognizes these names:

  NotoSansJP-Regular.ttf
  SourceHanSansJP-Regular.otf
  BIZUDGothic-Regular.ttf

DejaVuSans.ttf and DejaVuSansMono.ttf are kept only as a last-resort fallback.
They do not contain Japanese glyphs, so Japanese text will be garbled or shown
as missing-glyph boxes if no CJK font is present.

Emoji font (bundled):

  OpenMoji-black-glyf.ttf   # CC BY 4.0 — see LICENSE-OpenMoji.txt
  LICENSE-OpenMoji.txt

After adding a font, re-run kindle/install/deploy.sh to push it to the Kindle.
