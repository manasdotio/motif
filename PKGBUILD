# Maintainer: Motif Contributors <https://github.com/manasdotio/motif>
pkgname=motif
pkgver=1.0.1
pkgrel=1
pkgdesc="Native GTK4 + Libadwaita desktop theme manager for GNOME"
arch=('any')
url="https://github.com/manasdotio/motif"
license=('GPL3')
depends=('python' 'gtk4' 'libadwaita' 'python-gobject' 'python-httpx')
makedepends=('python-build' 'python-installer' 'python-setuptools' 'python-wheel')
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')

build() {
  cd "$pkgname-$pkgver"
  python -m build --wheel --no-isolation
}

package() {
  cd "$pkgname-$pkgver"
  python -m installer --destdir="$pkgdir" dist/*.whl

  install -Dm644 org.gnome.Motif.desktop "$pkgdir/usr/share/applications/org.gnome.Motif.desktop"
  install -Dm644 org.gnome.Motif.metainfo.xml "$pkgdir/usr/share/metainfo/org.gnome.Motif.metainfo.xml"
  install -Dm644 org.gnome.Motif.svg "$pkgdir/usr/share/icons/hicolor/scalable/apps/org.gnome.Motif.svg"
  install -Dm644 org.gnome.Motif-symbolic.svg "$pkgdir/usr/share/icons/hicolor/symbolic/apps/org.gnome.Motif-symbolic.svg"
  install -Dm644 motif/data/org.gnome.Motif.gschema.xml "$pkgdir/usr/share/glib-2.0/schemas/org.gnome.Motif.gschema.xml"
}
