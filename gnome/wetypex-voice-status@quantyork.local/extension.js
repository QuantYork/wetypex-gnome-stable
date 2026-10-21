import Clutter from 'gi://Clutter';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import {presentation} from './presentation.js';

const BUS = 'io.github.QuantYork.WeTypeX.VoiceStatus';
const PATH = '/io/github/QuantYork/WeTypeX/VoiceStatus';

export default class VoiceStatusExtension extends Extension {
    enable() {
        this._enabled = true;
        this._pending = false;
        this._cancellable = new Gio.Cancellable();
        this._indicator = new PanelMenu.Button(0.0, 'WeTypeX voice status', true);
        this._indicator.reactive = false;
        this._indicator.can_focus = false;
        this._box = new St.BoxLayout({style_class: 'panel-status-menu-box wetypex-voice-status', reactive: false});
        this._icon = new St.Icon({icon_name: 'audio-input-microphone-symbolic', style_class: 'system-status-icon'});
        this._label = new St.Label({y_align: Clutter.ActorAlign.CENTER});
        this._box.add_child(this._icon);
        this._box.add_child(this._label);
        this._indicator.add_child(this._box);
        Main.panel.addToStatusArea(this.uuid, this._indicator, Main.panel._leftBox.get_n_children(), 'left');
        this._indicator.hide();
        this._poll();
        this._timer = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
            this._poll();
            return GLib.SOURCE_CONTINUE;
        });
    }

    _position() {
        // Append to the left group, so status text grows into its empty right side.
        // Never allocate space inside the system indicators on the right.
        const parent = Main.panel._leftBox;
        const item = this._indicator.container;
        if (item.get_parent() !== parent)
            return;
        const last = parent.get_n_children() - 1;
        if (parent.get_children()[last] !== item)
            parent.set_child_at_index(item, last);
    }

    _poll() {
        if (!this._enabled || this._pending)
            return;
        this._pending = true;
        Gio.DBus.session.call(BUS, PATH, BUS, 'Poll', null,
            new GLib.VariantType('(s)'), Gio.DBusCallFlags.NO_AUTO_START, 1000,
            this._cancellable, (connection, result) => {
                if (!this._enabled)
                    return;
                this._pending = false;
                try {
                    const [raw] = connection.call_finish(result).deepUnpack();
                    const state = presentation(JSON.parse(raw));
                    if (!state) {
                        this._indicator.hide();
                        return;
                    }
                    this._label.text = state.text;
                    this._icon.icon_name = state.icon;
                    this._box.style_class = `panel-status-menu-box wetypex-voice-status ${state.color}`;
                    this._indicator.accessible_name = state.detail;
                    this._position();
                    this._indicator.show();
                } catch {
                    this._indicator.hide();
                }
            });
    }

    disable() {
        this._enabled = false;
        this._cancellable?.cancel();
        this._cancellable = null;
        if (this._timer)
            GLib.Source.remove(this._timer);
        this._timer = 0;
        this._indicator?.destroy();
        this._indicator = null;
        this._box = this._icon = this._label = null;
    }
}
