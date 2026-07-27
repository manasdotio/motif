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
install -Dm644 org.gnome.Motif.desktop %{buildroot}%{_datadir}/applications/org.gnome.Motif.desktop
install -Dm644 org.gnome.Motif.metainfo.xml %{buildroot}%{_datadir}/metainfo/org.gnome.Motif.metainfo.xml
install -Dm644 org.gnome.Motif.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/org.gnome.Motif.svg
install -Dm644 org.gnome.Motif-symbolic.svg %{buildroot}%{_datadir}/icons/hicolor/symbolic/apps/org.gnome.Motif-symbolic.svg
install -Dm644 motif/data/org.gnome.Motif.gschema.xml %{buildroot}%{_datadir}/glib-2.0/schemas/org.gnome.Motif.gschema.xml

%files
%license LICENSE
%doc README.md
%{_bindir}/motif
%{python3_sitelib}/motif*
%{_datadir}/applications/org.gnome.Motif.desktop
%{_datadir}/metainfo/org.gnome.Motif.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/org.gnome.Motif.svg
%{_datadir}/icons/hicolor/symbolic/apps/org.gnome.Motif-symbolic.svg
%{_datadir}/glib-2.0/schemas/org.gnome.Motif.gschema.xml

%changelog
* Mon Jul 27 2026 Motif Contributors <https://github.com/manasdotio/motif> - 1.0.1-1
- Initial RPM release of Motif 1.0.1
