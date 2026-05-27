# Cheerie

I made a small Windows desktop cat so work feels slightly less doomed.

It is called **Cheerie**. Its Korean name is **응원이**, which basically means a little friend that cheers you on.

It watches you type. Not the actual letters, just the fact that you are typing.

Type a little and the cat cheers. Type more and the cat cheers harder. Type too much and you get red full-power emotional support. Hover or hold-click it and it sends hearts.

This is not productivity science. It is just a small baby cat on your desktop yelling emotional support at you.

Also, small warning: I am a Korean normie who does not really know English, so yes, some English text went through AI. Please forgive the suspiciously organized sentences.

![Cheerie typing demo](media/demo.gif)

## Features

- Type = cat cheers
- Type more = cat cheers harder
- Type too much = red overpowered cheer mode
- Hover/click = hearts
- Multiple reminder alarms
- Custom message text for each alarm popup
- English/Korean UI setting
- Flip horizontal/vertical from the right-click menu
- Stores settings in Windows Registry, so the exe can be used without a separate JSON file
- PyInstaller build script for creating a standalone exe

## Run From Source

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python cheerie.py
```

## Build Exe

```powershell
.\build_public.bat
```

The output will be created at:

```text
dist\Cheerie.exe
```

For a ready-made Windows build, check the GitHub Releases page.

## Privacy

No account. No server. No tracking. No typed text saved.

Cheerie reacts to input events, not key contents. Settings are stored at:

```text
HKEY_CURRENT_USER\Software\Cheerie
```

Yes, I know a random exe from the internet sounds cursed. That is why the source is here too.

## Suggested GitHub Topics

`python`, `tkinter`, `windows`, `desktop-pet`, `keyboard`, `pynput`, `pyinstaller`, `reminder`, `vibe-coding`, `beginner-friendly`, `cat`

## 한국어

Cheerie는 **응원이**의 영어 이름입니다. 키보드와 마우스 입력량에 반응하는 작은 Windows 데스크탑 고양이예요.

조금 타이핑하면 입을 벌려 응원하고, 계속 두드리면 노란 별이 뜨다가 빨간 풀파워 응원 모드가 됩니다. 마우스를 올리거나 꾹 누르면 하트도 보냅니다.

거창한 생산성 앱은 아니고, 그냥 일할 때 바탕화면에서 아기 고양이 보면서 조금 덜 삭막하게 일하자는 느낌의 가벼운 밈 앱입니다.

- 우클릭 메뉴에서 설정, 반전, 알람 테스트, 종료 가능
- 알람 여러 개 추가 가능
- 알람마다 표시할 문구 설정 가능
- 설정에서 English/한국어 선택 가능
- 로그인 없음, 서버 없음, 추적 없음
- 입력된 키 내용은 저장하지 않고 입력 이벤트에만 반응합니다
