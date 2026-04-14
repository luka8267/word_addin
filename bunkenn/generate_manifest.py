import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent
STATIC_ROOT = ROOT / "azure-static-web-apps" / "static"
BASE_URL = "__BASE_URL__"
MINIMAL_ADDIN_ID = "__MINIMAL_ADDIN_ID__"
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
    <Hosts>
      <Host xsi:type="WordHost">
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


def render_manifest(template: str, *, base_url: str, addin_id: str) -> str:
    return (
        template.replace(BASE_URL, base_url)
        .replace(MINIMAL_ADDIN_ID, addin_id)
        .replace(FULL_ADDIN_ID, addin_id)
    )


def write_manifest(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    print(f"generated: {path}")


def main() -> None:
    base_url = os.getenv("BUNKEN_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not base_url:
        raise SystemExit("BUNKEN_PUBLIC_BASE_URL is required")
    if not base_url.startswith("https://"):
        raise SystemExit("BUNKEN_PUBLIC_BASE_URL must start with https://")

    minimal_id = os.getenv("BUNKEN_WORD_ADDIN_MINIMAL_ID", "F97D2F69-8FED-4054-83DA-3AA92DBC2F40").strip()
    full_id = os.getenv("BUNKEN_WORD_ADDIN_FULL_ID", "4E4651A8-424E-4C61-994A-1F7A3365874D").strip()

    write_manifest(
        ROOT / "manifest.minimal.xml",
        render_manifest(MINIMAL_MANIFEST, base_url=base_url, addin_id=minimal_id),
    )
    full_manifest = render_manifest(FULL_MANIFEST, base_url=base_url, addin_id=full_id)
    write_manifest(ROOT / "manifest.full.xml", full_manifest)
    write_manifest(ROOT / "manifest.production.xml", full_manifest)

    if not (STATIC_ROOT / "taskpane.minimal.html").exists():
        print("warning: taskpane.minimal.html was not found under azure-static-web-apps/static")


if __name__ == "__main__":
    main()
