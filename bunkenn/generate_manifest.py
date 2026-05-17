import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "azure-static-web-apps" / "static"
BASE_URL = "__BASE_URL__"
MINIMAL_ADDIN_ID = "__MINIMAL_ADDIN_ID__"
COMMANDS_ADDIN_ID = "__COMMANDS_ADDIN_ID__"
ICONS_ADDIN_ID = "__ICONS_ADDIN_ID__"
FULL_ADDIN_ID = "__FULL_ADDIN_ID__"

MINIMAL_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<OfficeApp
  xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:type="TaskPaneApp">
  <Id>__MINIMAL_ADDIN_ID__</Id>
  <Version>1.0.0.0</Version>
  <ProviderName>bunken</ProviderName>
  <DefaultLocale>ja-JP</DefaultLocale>
  <DisplayName DefaultValue="bunken Word (Minimal)"/>
  <Description DefaultValue="Minimal task pane manifest for bunken Word diagnostics."/>
  <IconUrl DefaultValue="__BASE_URL__/assets/icon-32.png"/>
  <HighResolutionIconUrl DefaultValue="__BASE_URL__/assets/icon-80.png"/>
  <SupportUrl DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
  <AppDomains>
    <AppDomain>__BASE_URL__</AppDomain>
  </AppDomains>
  <Hosts>
    <Host Name="Document"/>
  </Hosts>
  <DefaultSettings>
    <SourceLocation DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
  </DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions>
</OfficeApp>
"""

FULL_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<OfficeApp
  xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
  xmlns:ov="http://schemas.microsoft.com/office/taskpaneappversionoverrides"
  xsi:type="TaskPaneApp">
  <Id>__FULL_ADDIN_ID__</Id>
  <Version>1.0.0.0</Version>
  <ProviderName>bunken</ProviderName>
  <DefaultLocale>ja-JP</DefaultLocale>
  <DisplayName DefaultValue="bunken Word"/>
  <Description DefaultValue="Word citation and bibliography add-in for bunken"/>
  <IconUrl DefaultValue="__BASE_URL__/assets/icon-32.png"/>
  <HighResolutionIconUrl DefaultValue="__BASE_URL__/assets/icon-80.png"/>
  <SupportUrl DefaultValue="__BASE_URL__/taskpane.html"/>
  <AppDomains>
    <AppDomain>__BASE_URL__</AppDomain>
  </AppDomains>
  <Hosts>
    <Host Name="Document"/>
  </Hosts>
  <DefaultSettings>
    <SourceLocation DefaultValue="__BASE_URL__/taskpane.html"/>
  </DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions>
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/taskpaneappversionoverrides" xsi:type="VersionOverridesV1_0">
    <Requirements>
      <bt:Sets DefaultMinVersion="1.1">
        <bt:Set Name="AddinCommands" MinVersion="1.1"/>
      </bt:Sets>
    </Requirements>
    <Hosts>
      <Host xsi:type="Document">
        <DesktopFormFactor>
          <GetStarted>
            <Title resid="GetStarted.Title"/>
            <Description resid="GetStarted.Description"/>
            <LearnMoreUrl resid="GetStarted.LearnMoreUrl"/>
          </GetStarted>
          <FunctionFile resid="Commands.Url"/>
          <ExtensionPoint xsi:type="PrimaryCommandSurface">
            <OfficeTab id="TabHome">
              <Group id="Bunken.Group">
                <Label resid="Bunken.GroupLabel"/>
                <Icon>
                  <bt:Image size="16" resid="Icon.16"/>
                  <bt:Image size="32" resid="Icon.32"/>
                  <bt:Image size="80" resid="Icon.80"/>
                </Icon>
                <Control xsi:type="Button" id="Bunken.OpenTaskpane">
                  <Label resid="Bunken.OpenTaskpane.Label"/>
                  <Supertip>
                    <Title resid="Bunken.OpenTaskpane.Label"/>
                    <Description resid="Bunken.OpenTaskpane.Description"/>
                  </Supertip>
                  <Icon>
                    <bt:Image size="16" resid="Icon.16"/>
                    <bt:Image size="32" resid="Icon.32"/>
                    <bt:Image size="80" resid="Icon.80"/>
                  </Icon>
                  <Action xsi:type="ShowTaskpane">
                    <TaskpaneId>ButtonId1</TaskpaneId>
                    <SourceLocation resid="Taskpane.Url"/>
                  </Action>
                </Control>
              </Group>
            </OfficeTab>
          </ExtensionPoint>
        </DesktopFormFactor>
      </Host>
    </Hosts>
    <Resources>
      <bt:Images>
        <bt:Image id="Icon.16" DefaultValue="__BASE_URL__/assets/icon-16.png"/>
        <bt:Image id="Icon.32" DefaultValue="__BASE_URL__/assets/icon-32.png"/>
        <bt:Image id="Icon.80" DefaultValue="__BASE_URL__/assets/icon-80.png"/>
      </bt:Images>
      <bt:Urls>
        <bt:Url id="GetStarted.LearnMoreUrl" DefaultValue="__BASE_URL__/taskpane.html"/>
        <bt:Url id="Commands.Url" DefaultValue="__BASE_URL__/commands.html"/>
        <bt:Url id="Taskpane.Url" DefaultValue="__BASE_URL__/taskpane.html"/>
      </bt:Urls>
      <bt:ShortStrings>
        <bt:String id="GetStarted.Title" DefaultValue="bunken Word"/>
        <bt:String id="Bunken.GroupLabel" DefaultValue="bunken"/>
        <bt:String id="Bunken.OpenTaskpane.Label" DefaultValue="Open bunken"/>
      </bt:ShortStrings>
      <bt:LongStrings>
        <bt:String id="GetStarted.Description" DefaultValue="Manage citations and bibliography from bunken."/>
        <bt:String id="Bunken.OpenTaskpane.Description" DefaultValue="Open the bunken citation panel."/>
      </bt:LongStrings>
    </Resources>
  </VersionOverrides>
</OfficeApp>
"""

COMMANDS_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<OfficeApp
  xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
  xmlns:ov="http://schemas.microsoft.com/office/taskpaneappversionoverrides"
  xsi:type="TaskPaneApp">
  <Id>__COMMANDS_ADDIN_ID__</Id>
  <Version>1.0.0.0</Version>
  <ProviderName>bunken</ProviderName>
  <DefaultLocale>ja-JP</DefaultLocale>
  <DisplayName DefaultValue="bunken Word (Commands)"/>
  <Description DefaultValue="VersionOverrides diagnostic manifest for bunken Word."/>
  <IconUrl DefaultValue="__BASE_URL__/assets/icon-32.png"/>
  <HighResolutionIconUrl DefaultValue="__BASE_URL__/assets/icon-80.png"/>
  <SupportUrl DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
  <AppDomains>
    <AppDomain>__BASE_URL__</AppDomain>
  </AppDomains>
  <Hosts>
    <Host Name="Document"/>
  </Hosts>
  <DefaultSettings>
    <SourceLocation DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
  </DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions>
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/taskpaneappversionoverrides" xsi:type="VersionOverridesV1_0">
    <Requirements>
      <bt:Sets DefaultMinVersion="1.1">
        <bt:Set Name="AddinCommands" MinVersion="1.1"/>
      </bt:Sets>
    </Requirements>
    <Hosts>
      <Host xsi:type="Document">
        <DesktopFormFactor>
          <GetStarted>
            <Title resid="GetStarted.Title"/>
            <Description resid="GetStarted.Description"/>
            <LearnMoreUrl resid="GetStarted.LearnMoreUrl"/>
          </GetStarted>
          <FunctionFile resid="Commands.Url"/>
          <ExtensionPoint xsi:type="PrimaryCommandSurface">
            <OfficeTab id="TabHome">
              <Group id="Bunken.Group">
                <Label resid="Bunken.GroupLabel"/>
                <Icon>
                  <bt:Image size="16" resid="Icon.16"/>
                  <bt:Image size="32" resid="Icon.32"/>
                  <bt:Image size="80" resid="Icon.80"/>
                </Icon>
                <Control xsi:type="Button" id="Bunken.OpenTaskpane">
                  <Label resid="Bunken.OpenTaskpane.Label"/>
                  <Supertip>
                    <Title resid="Bunken.OpenTaskpane.Label"/>
                    <Description resid="Bunken.OpenTaskpane.Description"/>
                  </Supertip>
                  <Icon>
                    <bt:Image size="16" resid="Icon.16"/>
                    <bt:Image size="32" resid="Icon.32"/>
                    <bt:Image size="80" resid="Icon.80"/>
                  </Icon>
                  <Action xsi:type="ShowTaskpane">
                    <TaskpaneId>ButtonId1</TaskpaneId>
                    <SourceLocation resid="Taskpane.Url"/>
                  </Action>
                </Control>
              </Group>
            </OfficeTab>
          </ExtensionPoint>
        </DesktopFormFactor>
      </Host>
    </Hosts>
    <Resources>
      <bt:Images>
        <bt:Image id="Icon.16" DefaultValue="__BASE_URL__/assets/icon-16.png"/>
        <bt:Image id="Icon.32" DefaultValue="__BASE_URL__/assets/icon-32.png"/>
        <bt:Image id="Icon.80" DefaultValue="__BASE_URL__/assets/icon-80.png"/>
      </bt:Images>
      <bt:Urls>
        <bt:Url id="GetStarted.LearnMoreUrl" DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
        <bt:Url id="Commands.Url" DefaultValue="__BASE_URL__/commands.html"/>
        <bt:Url id="Taskpane.Url" DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
      </bt:Urls>
      <bt:ShortStrings>
        <bt:String id="GetStarted.Title" DefaultValue="bunken Word"/>
        <bt:String id="Bunken.GroupLabel" DefaultValue="bunken"/>
        <bt:String id="Bunken.OpenTaskpane.Label" DefaultValue="Open bunken"/>
      </bt:ShortStrings>
      <bt:LongStrings>
        <bt:String id="GetStarted.Description" DefaultValue="Open the diagnostic task pane."/>
        <bt:String id="Bunken.OpenTaskpane.Description" DefaultValue="Open the diagnostic task pane."/>
      </bt:LongStrings>
    </Resources>
  </VersionOverrides>
</OfficeApp>
"""

ICONS_MANIFEST = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<OfficeApp
  xmlns="http://schemas.microsoft.com/office/appforoffice/1.1"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xmlns:bt="http://schemas.microsoft.com/office/officeappbasictypes/1.0"
  xmlns:ov="http://schemas.microsoft.com/office/taskpaneappversionoverrides"
  xsi:type="TaskPaneApp">
  <Id>__ICONS_ADDIN_ID__</Id>
  <Version>1.0.0.0</Version>
  <ProviderName>bunken</ProviderName>
  <DefaultLocale>ja-JP</DefaultLocale>
  <DisplayName DefaultValue="bunken Word (Icons)"/>
  <Description DefaultValue="Icon resource diagnostic manifest for bunken Word."/>
  <IconUrl DefaultValue="__BASE_URL__/assets/icon-32.png"/>
  <HighResolutionIconUrl DefaultValue="__BASE_URL__/assets/icon-80.png"/>
  <SupportUrl DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
  <AppDomains>
    <AppDomain>__BASE_URL__</AppDomain>
  </AppDomains>
  <Hosts>
    <Host Name="Document"/>
  </Hosts>
  <DefaultSettings>
    <SourceLocation DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
  </DefaultSettings>
  <Permissions>ReadWriteDocument</Permissions>
  <VersionOverrides xmlns="http://schemas.microsoft.com/office/taskpaneappversionoverrides" xsi:type="VersionOverridesV1_0">
    <Requirements>
      <bt:Sets DefaultMinVersion="1.1">
        <bt:Set Name="AddinCommands" MinVersion="1.1"/>
      </bt:Sets>
    </Requirements>
    <Hosts>
      <Host xsi:type="Document">
        <DesktopFormFactor>
          <GetStarted>
            <Title resid="GetStarted.Title"/>
            <Description resid="GetStarted.Description"/>
            <LearnMoreUrl resid="GetStarted.LearnMoreUrl"/>
          </GetStarted>
          <FunctionFile resid="Commands.Url"/>
          <ExtensionPoint xsi:type="PrimaryCommandSurface">
            <OfficeTab id="TabHome">
              <Group id="Bunken.Group">
                <Label resid="Bunken.GroupLabel"/>
                <Icon>
                  <bt:Image size="16" resid="Icon.16"/>
                  <bt:Image size="32" resid="Icon.32"/>
                  <bt:Image size="80" resid="Icon.80"/>
                </Icon>
                <Control xsi:type="Button" id="Bunken.OpenTaskpane">
                  <Label resid="Bunken.OpenTaskpane.Label"/>
                  <Supertip>
                    <Title resid="Bunken.OpenTaskpane.Label"/>
                    <Description resid="Bunken.OpenTaskpane.Description"/>
                  </Supertip>
                  <Icon>
                    <bt:Image size="16" resid="Icon.16"/>
                    <bt:Image size="32" resid="Icon.32"/>
                    <bt:Image size="80" resid="Icon.80"/>
                  </Icon>
                  <Action xsi:type="ShowTaskpane">
                    <TaskpaneId>ButtonId1</TaskpaneId>
                    <SourceLocation resid="Taskpane.Url"/>
                  </Action>
                </Control>
              </Group>
            </OfficeTab>
          </ExtensionPoint>
        </DesktopFormFactor>
      </Host>
    </Hosts>
    <Resources>
      <bt:Images>
        <bt:Image id="Icon.16" DefaultValue="__BASE_URL__/assets/icon-16.png"/>
        <bt:Image id="Icon.32" DefaultValue="__BASE_URL__/assets/icon-32.png"/>
        <bt:Image id="Icon.80" DefaultValue="__BASE_URL__/assets/icon-80.png"/>
      </bt:Images>
      <bt:Urls>
        <bt:Url id="GetStarted.LearnMoreUrl" DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
        <bt:Url id="Commands.Url" DefaultValue="__BASE_URL__/commands.html"/>
        <bt:Url id="Taskpane.Url" DefaultValue="__BASE_URL__/taskpane.minimal.html"/>
      </bt:Urls>
      <bt:ShortStrings>
        <bt:String id="GetStarted.Title" DefaultValue="bunken Word"/>
        <bt:String id="Bunken.GroupLabel" DefaultValue="bunken"/>
        <bt:String id="Bunken.OpenTaskpane.Label" DefaultValue="Open bunken"/>
      </bt:ShortStrings>
      <bt:LongStrings>
        <bt:String id="GetStarted.Description" DefaultValue="Open the diagnostic task pane."/>
        <bt:String id="Bunken.OpenTaskpane.Description" DefaultValue="Open the diagnostic task pane."/>
      </bt:LongStrings>
    </Resources>
  </VersionOverrides>
</OfficeApp>
"""


def render_manifest(template: str, *, base_url: str, addin_id: str) -> str:
    return (
        template.replace(BASE_URL, base_url)
        .replace(MINIMAL_ADDIN_ID, addin_id)
        .replace(COMMANDS_ADDIN_ID, addin_id)
        .replace(ICONS_ADDIN_ID, addin_id)
        .replace(FULL_ADDIN_ID, addin_id)
    )


def write_manifest(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    print(f"generated: {path}")


def require_https_base_url(base_url: str) -> None:
    if not base_url.startswith("https://"):
        raise SystemExit("BUNKEN_PUBLIC_BASE_URL must start with https://")


def require_local_base_url(base_url: str) -> None:
    allowed_prefixes = (
        "http://localhost:",
        "https://localhost:",
        "http://127.0.0.1:",
        "https://127.0.0.1:",
    )
    if not base_url.startswith(allowed_prefixes):
        raise SystemExit(
            "BUNKEN_LOCAL_BASE_URL must use localhost or 127.0.0.1, "
            "for example http://localhost:4280"
        )


def generate_production_manifests() -> None:
    base_url = os.getenv("BUNKEN_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise SystemExit("BUNKEN_PUBLIC_BASE_URL is required")
    require_https_base_url(base_url)

    minimal_id = os.getenv("BUNKEN_WORD_ADDIN_MINIMAL_ID", "F97D2F69-8FED-4054-83DA-3AA92DBC2F40").strip()
    commands_id = os.getenv("BUNKEN_WORD_ADDIN_COMMANDS_ID", "8D0956B7-78B2-4AD8-9858-25E01E8D13D4").strip()
    icons_id = os.getenv("BUNKEN_WORD_ADDIN_ICONS_ID", "EAFB6601-2F2F-4F9C-9B96-1B8317A13659").strip()
    full_id = os.getenv("BUNKEN_WORD_ADDIN_FULL_ID", "4E4651A8-424E-4C61-994A-1F7A3365874D").strip()

    write_manifest(
        ROOT / "manifest.minimal.xml",
        render_manifest(MINIMAL_MANIFEST, base_url=base_url, addin_id=minimal_id),
    )
    write_manifest(
        ROOT / "manifest.commands.xml",
        render_manifest(COMMANDS_MANIFEST, base_url=base_url, addin_id=commands_id),
    )
    write_manifest(
        ROOT / "manifest.icons.xml",
        render_manifest(ICONS_MANIFEST, base_url=base_url, addin_id=icons_id),
    )
    full_manifest = render_manifest(FULL_MANIFEST, base_url=base_url, addin_id=full_id)
    write_manifest(ROOT / "manifest.full.xml", full_manifest)
    write_manifest(ROOT / "manifest.production.xml", full_manifest)

    if not (STATIC_ROOT / "taskpane.minimal.html").exists():
        print("warning: taskpane.minimal.html was not found under azure-static-web-apps/static")


def generate_local_manifests() -> None:
    base_url = os.getenv("BUNKEN_LOCAL_BASE_URL", "https://localhost:4280").strip().rstrip("/")
    require_local_base_url(base_url)

    minimal_id = os.getenv("BUNKEN_WORD_ADDIN_LOCAL_MINIMAL_ID", "7D30D056-54CF-4D7A-A8D3-5002E1C034B1").strip()
    commands_id = os.getenv("BUNKEN_WORD_ADDIN_LOCAL_COMMANDS_ID", "68BB8312-86B9-430E-BC61-6B4DF8183703").strip()
    icons_id = os.getenv("BUNKEN_WORD_ADDIN_LOCAL_ICONS_ID", "31539597-94E9-4509-BAC6-66987975D55D").strip()
    full_id = os.getenv("BUNKEN_WORD_ADDIN_LOCAL_ID", "A8C349E2-742D-499D-A5CF-0CDDF6CE5CD1").strip()

    write_manifest(
        ROOT / "manifest.local.minimal.xml",
        render_manifest(MINIMAL_MANIFEST, base_url=base_url, addin_id=minimal_id),
    )
    write_manifest(
        ROOT / "manifest.local.commands.xml",
        render_manifest(COMMANDS_MANIFEST, base_url=base_url, addin_id=commands_id),
    )
    write_manifest(
        ROOT / "manifest.local.icons.xml",
        render_manifest(ICONS_MANIFEST, base_url=base_url, addin_id=icons_id),
    )
    full_manifest = render_manifest(FULL_MANIFEST, base_url=base_url, addin_id=full_id)
    write_manifest(ROOT / "manifest.local.full.xml", full_manifest)
    write_manifest(ROOT / "manifest.local.xml", full_manifest)


def main() -> None:
    if len(sys.argv) > 2:
        raise SystemExit("usage: python generate_manifest.py [--local]")
    if len(sys.argv) == 2:
        if sys.argv[1] != "--local":
            raise SystemExit("usage: python generate_manifest.py [--local]")
        generate_local_manifests()
        return

    generate_production_manifests()


if __name__ == "__main__":
    main()
