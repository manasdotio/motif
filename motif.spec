Name:           motif
Version:        1.0.1
Release:        1%{?dist}
Summary:        Native GTK4 + Libadwaita desktop theme manager for GNOME

License:        GPL-3.0-or-later
URL:            https://github.com/manasdotio/motif
Source0:        %{url}/archive/refs/tags/v%{version}.tar.gz

BuildArch:      noarch
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pip
BuildRequires:  python3-wheel

Requires:       python3 >= 3.11
Requires:       gtk4
Requires:       libadwaita
Requires:       python3-gobject
Requires:       python3-httpx

%description
Motif is a native GTK4 and Libadwaita desktop application for GNOME that brings
a smooth, one-click experience to browsing, downloading, applying, and managing
GTK, Shell, Icon, and Cursor themes.

%prep
%autosetup -n motif-%{version}

%build
%py3_build

%install
%py3_install
install -Dm644 io.github.manasdotio.motif.desktop %{buildroot}%{_datadir}/applications/io.github.manasdotio.motif.desktop
install -Dm644 io.github.manasdotio.motif.metainfo.xml %{buildroot}%{_datadir}/metainfo/io.github.manasdotio.motif.metainfo.xml
install -Dm644 io.github.manasdotio.motif.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.manasdotio.motif.svg
install -Dm644 io.github.manasdotio.motif-symbolic.svg %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps/io.github.manasdotio.motif-symbolic.svg
install -Dm644 motif/data/io.github.manasdotio.motif.gschema.xml %{buildroot}%{_datadir}/glib-2.0/schemas/io.github.manasdotio.motif.gschema.xml

%files
%license LICENSE
%doc README.md
%{_bindir}/motif
%{python3_sitelib}/motif*
%{_datadir}/applications/io.github.manasdotio.motif.desktop
%{_datadir}/metainfo/io.github.manasdotio.motif.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.manasdotio.motif.svg
%{_datadir}/icons/hicolor/symbolic/apps/io.github.manasdotio.motif-symbolic.svg
%{_datadir}/glib-2.0/schemas/io.github.manasdotio.motif.gschema.xml

%changelog
* Mon Jul 27 2026 Motif Contributors <https://github.com/manasdotio/motif> - 1.0.1-1
- Initial RPM release of Motif 1.0.1
