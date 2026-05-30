#define MyAppName "Morsewurst"
#define MyAppVersion "0.99.11.3"
#define MyAppPublisher "Kasperi Koski"
#define MyAppExeName "Morsewurst.exe"

[Setup]
AppId={{f6ba2c5f-0a3f-4fac-80fb-13d81e2c3e45}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=MorsewurstSetup_{#MyAppVersion}
SetupIconFile=assets\morse.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=yes
DisableWelcomePage=no
LicenseFile=licenses\license_fi.txt
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "finnish"; MessagesFile: "compiler:Languages\Finnish.isl"; LicenseFile: "licenses\license_fi.txt"
Name: "english"; MessagesFile: "compiler:Default.isl"; LicenseFile: "licenses\license_en.txt"
Name: "swedish"; MessagesFile: "compiler:Languages\Swedish.isl"; LicenseFile: "licenses\license_sv.txt"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"; LicenseFile: "licenses\license_ja.txt"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"; LicenseFile: "licenses\license_fr.txt"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"; LicenseFile: "licenses\license_it.txt"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"; LicenseFile: "licenses\license_es.txt"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"; LicenseFile: "licenses\license_de.txt"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"; LicenseFile: "licenses\license_ru.txt"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"; LicenseFile: "licenses\license_pt.txt"
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"; LicenseFile: "licenses\license_ko.txt"

[Messages]
finnish.WelcomeLabel1=Tervetuloa Morsewurstin asennukseen
finnish.WelcomeLabel2=Tervehdys, hyvä Morsen ystävä.%n%nKiitos mielenkiinnostasi Morsewurstia kohtaan. Ohjelma on vielä keskeneräinen ja matkalla kohti parempaa muotoaan, mutta juuri sinun palautteesi, havaintosi ja kehitysideasi voivat tehdä siitä aidosti hyödyllisen ja entistä maukkaamman setin Morsen harjoitteluun.%n%nJos huomaat virheitä, saat hyvän idean tai haluat muuten vain lähettää terveisiä, voit ottaa yhteyttä osoitteeseen morsewurst@kasperikoski.fi.%n%nSeuraavaksi tulee se tylsä osio. Käyttöehdot ja vastuuvapauslausekkeet.

english.WelcomeLabel1=Welcome to the Morsewurst Setup Wizard
english.WelcomeLabel2=Greetings, dear Morse friend.%n%nThank you for your interest in Morsewurst. The program is still unfinished and on its way toward a better form, but your feedback, observations and development ideas can help make it genuinely useful and an even tastier set for Morse practice.%n%nIf you notice bugs, have a good idea or just want to send a message, you can contact me at morsewurst@kasperikoski.fi.%n%nNext comes the boring part. Terms of use and disclaimer.

swedish.WelcomeLabel1=Välkommen till installationen av Morsewurst
swedish.WelcomeLabel2=Hälsningar, kära Morsetelegrafivän.%n%nTack för ditt intresse för Morsewurst. Programmet är fortfarande ofärdigt och på väg mot en bättre form, men din återkoppling, dina iakttagelser och dina utvecklingsidéer kan göra det genuint användbart och till ett ännu smakligare paket för Morseträning.%n%nOm du märker fel, får en bra idé eller bara vill skicka en hälsning kan du kontakta mig på morsewurst@kasperikoski.fi.%n%nNu kommer den tråkiga delen. Användarvillkor och ansvarsfriskrivning.

japanese.WelcomeLabel1=Morsewurst セットアップへようこそ
japanese.WelcomeLabel2=こんにちは、モールスの友よ。%n%nMorsewurst に興味を持っていただき、ありがとうございます。このプログラムはまだ未完成で、より良い形へ向かっている途中です。あなたからのフィードバック、気づき、開発アイデアがあれば、モールス練習のために本当に役立つ、さらにおいしいセットにしていくことができます。%n%n不具合を見つけた場合、良いアイデアがある場合、または単にメッセージを送りたい場合は、morsewurst@kasperikoski.fi までご連絡ください。%n%n次は退屈な部分です。利用規約と免責事項です。

french.WelcomeLabel1=Bienvenue dans l'installation de Morsewurst
french.WelcomeLabel2=Bonjour, cher ami du Morse.%n%nMerci de votre intérêt pour Morsewurst. Le programme est encore inachevé et poursuit son chemin vers une meilleure forme, mais vos retours, observations et idées de développement peuvent le rendre réellement utile et encore plus savoureux pour l'entraînement au Morse.%n%nSi vous remarquez des erreurs, avez une bonne idée ou souhaitez simplement envoyer un message, vous pouvez me contacter à morsewurst@kasperikoski.fi.%n%nVient maintenant la partie ennuyeuse. Conditions d'utilisation et clause de non-responsabilité.

italian.WelcomeLabel1=Benvenuto nell'installazione di Morsewurst
italian.WelcomeLabel2=Un saluto, caro amico del Morse.%n%nGrazie per il tuo interesse verso Morsewurst. Il programma è ancora incompleto e sta cercando una forma migliore, ma il tuo feedback, le tue osservazioni e le tue idee di sviluppo possono renderlo davvero utile e un set ancora più gustoso per allenarsi con il Morse.%n%nSe noti errori, hai una buona idea o vuoi semplicemente mandare un saluto, puoi contattarmi all'indirizzo morsewurst@kasperikoski.fi.%n%nOra arriva la parte noiosa. Termini di utilizzo e dichiarazione di esclusione di responsabilità.

spanish.WelcomeLabel1=Bienvenido al instalador de Morsewurst
spanish.WelcomeLabel2=Saludos, querido amigo del Morse.%n%nGracias por tu interés en Morsewurst. El programa todavía está inacabado y va camino de una forma mejor, pero tus comentarios, observaciones e ideas de desarrollo pueden hacerlo realmente útil y convertirlo en un conjunto aún más sabroso para practicar Morse.%n%nSi encuentras errores, tienes una buena idea o simplemente quieres enviar un saludo, puedes escribirme a morsewurst@kasperikoski.fi.%n%nAhora viene la parte aburrida. Condiciones de uso y exención de responsabilidad.

german.WelcomeLabel1=Willkommen beim Setup von Morsewurst
german.WelcomeLabel2=Grüße, lieber Morsefreund.%n%nVielen Dank für dein Interesse an Morsewurst. Das Programm ist noch unfertig und auf dem Weg zu einer besseren Form, aber dein Feedback, deine Beobachtungen und deine Entwicklungsideen können es wirklich nützlich machen und zu einem noch schmackhafteren Paket für das Morsetraining werden lassen.%n%nWenn du Fehler bemerkst, eine gute Idee hast oder einfach eine Nachricht senden möchtest, kannst du mich unter morsewurst@kasperikoski.fi kontaktieren.%n%nAls Nächstes kommt der langweilige Teil. Nutzungsbedingungen und Haftungsausschluss.

russian.WelcomeLabel1=Добро пожаловать в установку Morsewurst
russian.WelcomeLabel2=Приветствую, дорогой друг азбуки Морзе.%n%nСпасибо за интерес к Morsewurst. Программа еще не завершена и движется к лучшей форме, но ваши отзывы, наблюдения и идеи по развитию могут сделать ее действительно полезной и еще более вкусным набором для тренировки Морзе.%n%nЕсли вы заметите ошибки, у вас появится хорошая идея или вы просто захотите передать привет, вы можете написать мне на morsewurst@kasperikoski.fi.%n%nДалее идет скучная часть. Условия использования и отказ от ответственности.

portuguese.WelcomeLabel1=Bem-vindo à instalação do Morsewurst
portuguese.WelcomeLabel2=Saudações, caro amigo do Morse.%n%nObrigado pelo seu interesse no Morsewurst. O programa ainda está inacabado e a caminho de uma forma melhor, mas o seu feedback, as suas observações e as suas ideias de desenvolvimento podem torná-lo realmente útil e num conjunto ainda mais saboroso para praticar Morse.%n%nSe encontrar erros, tiver uma boa ideia ou quiser simplesmente enviar uma saudação, pode contactar-me em morsewurst@kasperikoski.fi.%n%nA seguir vem a parte aborrecida. Termos de utilização e exclusão de responsabilidade.

korean.WelcomeLabel1=Morsewurst 설치 마법사에 오신 것을 환영합니다
korean.WelcomeLabel2=안녕하세요, 친애하는 모스 부호 친구 여러분.%n%nMorsewurst에 관심을 가져 주셔서 감사합니다. 이 프로그램은 아직 미완성이며 더 나은 모습으로 나아가는 중입니다. 여러분의 피드백, 발견한 점, 개발 아이디어가 이 프로그램을 정말 유용하고 모스 연습을 위한 더욱 맛있는 세트로 만들어 줄 수 있습니다.%n%n오류를 발견했거나 좋은 아이디어가 있거나 그냥 인사를 전하고 싶다면 morsewurst@kasperikoski.fi 로 연락할 수 있습니다.%n%n이제 지루한 부분이 이어집니다. 이용 약관 및 면책 조항입니다.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Morsewurst\*"; DestDir: "{app}"; Excludes: "network.gif,practice.gif"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "licenses\*.txt"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent