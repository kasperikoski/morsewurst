#define MyAppName "Morsewurst"
#define MyAppVersion "0.99.12.2"
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
finnish.WelcomeLabel2=Tervehdys, hyvä Morsen ystävä.%n%nKiitos mielenkiinnostasi Morsewurstia kohtaan. Ohjelma on vielä kehityksessä, ja palaute, virheilmoitukset sekä kehitysideat auttavat tekemään siitä paremman työkalun Morsen harjoitteluun.%n%nVoit ottaa yhteyttä osoitteeseen morsewurst@kasperikoski.fi.%n%nSeuraavaksi näytetään käyttöehdot ja vastuuvapauslauseke.

english.WelcomeLabel1=Welcome to the Morsewurst Setup Wizard
english.WelcomeLabel2=Greetings, dear Morse friend.%n%nThank you for your interest in Morsewurst. The program is still under development, and your feedback, bug reports and ideas can help make it a better tool for Morse practice.%n%nYou can contact me at morsewurst@kasperikoski.fi.%n%nNext, the terms of use and disclaimer will be shown.

swedish.WelcomeLabel1=Välkommen till installationen av Morsewurst
swedish.WelcomeLabel2=Hälsningar, kära Morsetelegrafivän.%n%nTack för ditt intresse för Morsewurst. Programmet är fortfarande under utveckling, och återkoppling, felrapporter och idéer hjälper till att göra det bättre för Morseträning.%n%nDu kan kontakta mig på morsewurst@kasperikoski.fi.%n%nHärnäst visas användarvillkor och ansvarsfriskrivning.

japanese.WelcomeLabel1=Morsewurst セットアップへようこそ
japanese.WelcomeLabel2=こんにちは、モールスの友よ。%n%nMorsewurst に興味を持っていただき、ありがとうございます。このプログラムはまだ開発中です。不具合の報告、フィードバック、改善案は、モールス練習ツールとしてより良くする助けになります。%n%n連絡先は morsewurst@kasperikoski.fi です。%n%n次に、利用規約と免責事項を表示します。

french.WelcomeLabel1=Bienvenue dans l'installation de Morsewurst
french.WelcomeLabel2=Bonjour, cher ami du Morse.%n%nMerci de votre intérêt pour Morsewurst. Le programme est encore en développement, et vos retours, rapports de bugs et idées peuvent aider à en faire un meilleur outil pour l'entraînement au Morse.%n%nVous pouvez me contacter à morsewurst@kasperikoski.fi.%n%nLes conditions d'utilisation et la clause de non-responsabilité vont maintenant s'afficher.

italian.WelcomeLabel1=Benvenuto nell'installazione di Morsewurst
italian.WelcomeLabel2=Un saluto, caro amico del Morse.%n%nGrazie per il tuo interesse verso Morsewurst. Il programma è ancora in sviluppo, e feedback, segnalazioni di errori e idee possono aiutare a renderlo uno strumento migliore per allenarsi con il Morse.%n%nPuoi contattarmi all'indirizzo morsewurst@kasperikoski.fi.%n%nOra verranno mostrati i termini di utilizzo e la dichiarazione di esclusione di responsabilità.

spanish.WelcomeLabel1=Bienvenido al instalador de Morsewurst
spanish.WelcomeLabel2=Saludos, querido amigo del Morse.%n%nGracias por tu interés en Morsewurst. El programa todavía está en desarrollo, y tus comentarios, informes de errores e ideas pueden ayudar a convertirlo en una mejor herramienta para practicar Morse.%n%nPuedes escribirme a morsewurst@kasperikoski.fi.%n%nA continuación se mostrarán las condiciones de uso y la exención de responsabilidad.

german.WelcomeLabel1=Willkommen beim Setup von Morsewurst
german.WelcomeLabel2=Grüße, lieber Morsefreund.%n%nVielen Dank für dein Interesse an Morsewurst. Das Programm befindet sich noch in Entwicklung, und Feedback, Fehlermeldungen sowie Ideen helfen dabei, es zu einem besseren Werkzeug für das Morsetraining zu machen.%n%nDu kannst mich unter morsewurst@kasperikoski.fi kontaktieren.%n%nAls Nächstes werden Nutzungsbedingungen und Haftungsausschluss angezeigt.

russian.WelcomeLabel1=Добро пожаловать в установку Morsewurst
russian.WelcomeLabel2=Приветствую, дорогой друг азбуки Морзе.%n%nСпасибо за интерес к Morsewurst. Программа все еще находится в разработке, и ваши отзывы, сообщения об ошибках и идеи помогут сделать ее лучшим инструментом для тренировки Морзе.%n%nВы можете написать мне на morsewurst@kasperikoski.fi.%n%nДалее будут показаны условия использования и отказ от ответственности.

portuguese.WelcomeLabel1=Bem-vindo à instalação do Morsewurst
portuguese.WelcomeLabel2=Saudações, caro amigo do Morse.%n%nObrigado pelo seu interesse no Morsewurst. O programa ainda está em desenvolvimento, e o seu feedback, relatórios de erros e ideias podem ajudar a torná-lo uma ferramenta melhor para praticar Morse.%n%nPode contactar-me em morsewurst@kasperikoski.fi.%n%nA seguir serão apresentados os termos de utilização e a exclusão de responsabilidade.

korean.WelcomeLabel1=Morsewurst 설치 마법사에 오신 것을 환영합니다
korean.WelcomeLabel2=안녕하세요, 친애하는 모스 부호 친구 여러분.%n%nMorsewurst에 관심을 가져 주셔서 감사합니다. 이 프로그램은 아직 개발 중이며, 피드백, 오류 보고, 개선 아이디어는 더 나은 모스 연습 도구를 만드는 데 도움이 됩니다.%n%n연락처는 morsewurst@kasperikoski.fi 입니다.%n%n다음으로 이용 약관과 면책 조항이 표시됩니다.

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