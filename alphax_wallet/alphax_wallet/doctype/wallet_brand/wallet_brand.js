// Wallet Brand form
// =================
// - Renders a live brand preview (hero card mock) using the current values
// - Extracts dominant colours from the uploaded logo (client-side Canvas)
// - "Generate Palette from Logo" derives the full palette server-side
// - "Activate for this Company" sets is_active and saves

frappe.ui.form.on("Wallet Brand", {
    refresh(frm) {
        render_preview(frm);
        render_logo_preview(frm);

        if (!frm.is_new()) {
            if (!frm.doc.is_active) {
                frm.add_custom_button(__("Activate for this Company"), () => {
                    frm.call("activate").then(() => {
                        frappe.show_alert({
                            message: __("Brand activated for {0}", [frm.doc.company]),
                            indicator: "green",
                        });
                        frm.reload_doc();
                    });
                }).addClass("btn-primary");
            } else {
                frm.dashboard.add_indicator(
                    __("Active brand for {0}", [frm.doc.company]),
                    "green"
                );
            }

            frm.add_custom_button(__("Preview on Dashboard"), () => {
                window.open(
                    `/app/alphax-wallet-dashboard?preview_brand=${encodeURIComponent(frm.doc.name)}`,
                    "_blank"
                );
            });
        }
    },

    // Re-render the preview when any branded field changes
    brand_display_name: render_preview,
    tagline: render_preview,
    logo: (frm) => { render_logo_preview(frm); render_preview(frm); },
    logo_on_dark: (frm) => { render_logo_preview(frm); render_preview(frm); },
    primary: render_preview,
    primary_dark: render_preview,
    primary_light: render_preview,
    accent: render_preview,
    accent_light: render_preview,
    pink: render_preview,
    pink_dark: render_preview,
    dark_base: render_preview,
    dark_mid: render_preview,
    dark_elev: render_preview,

    auto_generate_from_logo(frm) {
        if (!frm.doc.logo) {
            frappe.msgprint({
                title: __("No logo"),
                message: __("Upload a logo first."),
                indicator: "orange",
            });
            return;
        }
        extract_colors_from_logo(frm);
    },
});


// ---------------------------------------------------------------------------
// Logo → colour extraction (client-side Canvas)
// ---------------------------------------------------------------------------
function extract_colors_from_logo(frm) {
    frappe.show_progress(__("Extracting colours"), 10, 100);

    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
        frappe.show_progress(__("Extracting colours"), 40, 100);
        try {
            const colors = extract_dominant_colors(img, 5);
            frappe.show_progress(__("Deriving palette"), 70, 100);

            frm.call("auto_generate", {
                seed_colors: JSON.stringify({
                    primary: colors[0],
                    accent: colors[1],
                    pink: colors[2],
                    dark_base: colors[3] || colors[0],
                }),
            }).then(() => {
                frappe.hide_progress();
                frm.reload_doc();
                frappe.show_alert({
                    message: __("Palette generated from logo. Review and tweak before activating."),
                    indicator: "green",
                });
            });
        } catch (e) {
            frappe.hide_progress();
            frappe.msgprint({
                title: __("Extraction failed"),
                message: e.message || String(e),
                indicator: "red",
            });
        }
    };
    img.onerror = () => {
        frappe.hide_progress();
        frappe.msgprint(__("Could not load the logo image. Try a PNG or JPG under 2MB."));
    };
    img.src = frm.doc.logo;
}

function extract_dominant_colors(img, count) {
    const canvas = document.createElement("canvas");
    const maxDim = 200;
    const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
    canvas.width = Math.max(1, Math.floor(img.width * scale));
    canvas.height = Math.max(1, Math.floor(img.height * scale));
    const ctx = canvas.getContext("2d");
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

    let imgData;
    try {
        imgData = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    } catch (e) {
        throw new Error(__("Cannot read image pixels (CORS). Save the brand first, then try again."));
    }

    const buckets = new Map();
    for (let i = 0; i < imgData.length; i += 4) {
        const r = imgData[i], g = imgData[i + 1], b = imgData[i + 2], a = imgData[i + 3];
        if (a < 200) continue;
        const luma = 0.299 * r + 0.587 * g + 0.114 * b;
        if (luma > 240 || luma < 15) continue;
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        if (max - min < 20) continue;
        const key = `${r >> 5}-${g >> 5}-${b >> 5}`;
        const entry = buckets.get(key) || { r: 0, g: 0, b: 0, n: 0 };
        entry.r += r; entry.g += g; entry.b += b; entry.n++;
        buckets.set(key, entry);
    }

    if (buckets.size === 0) {
        throw new Error(__("Logo has no usable colours. Try a different image."));
    }

    const sorted = Array.from(buckets.values()).sort((a, b) => b.n - a.n);
    const colors = sorted.slice(0, count).map(e =>
        rgb_to_hex(Math.round(e.r / e.n), Math.round(e.g / e.n), Math.round(e.b / e.n))
    );
    colors.sort((a, b) => saturation(b) - saturation(a));
    return colors;
}

function saturation(hex) {
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    return max === 0 ? 0 : (max - min) / max;
}

function rgb_to_hex(r, g, b) {
    return "#" + [r, g, b].map(v =>
        Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0").toUpperCase()
    ).join("");
}


// ---------------------------------------------------------------------------
// Live preview — a mini dashboard hero showing how the brand will look
// ---------------------------------------------------------------------------
function render_preview(frm) {
    const d = frm.doc;
    const display_name = d.brand_display_name || d.brand_name || __("New Brand");
    const logo = d.logo_on_dark || d.logo;

    const html = `
        <div style="padding:24px 28px;margin:8px 0;border-radius:14px;
                    background:linear-gradient(135deg,
                        ${d.dark_base || '#18061F'} 0%,
                        ${d.dark_mid || '#2B1038'} 55%,
                        ${d.dark_elev || '#3C1745'} 100%);
                    color:${d.text_on_dark || '#F5EDEF'};
                    position:relative;overflow:hidden;
                    box-shadow:0 8px 24px rgba(0,0,0,0.15);">
            <div style="position:absolute;top:-30px;right:-30px;width:180px;height:180px;
                        border-radius:50%;
                        background:radial-gradient(circle, ${d.pink || '#D97A9E'}33 0%, transparent 70%);
                        pointer-events:none;"></div>
            <div style="position:relative;z-index:1;display:flex;align-items:center;gap:16px;flex-wrap:wrap;">
                ${logo
                    ? `<img src="${logo}" style="height:56px;width:56px;object-fit:contain;
                                                  background:rgba(255,255,255,0.08);
                                                  padding:6px;border-radius:12px;"/>`
                    : `<div style="width:56px;height:56px;border-radius:14px;
                                   background:linear-gradient(135deg, ${d.accent || '#D9A54A'} 0%, ${d.accent_light || '#F0C06A'} 100%);
                                   display:flex;align-items:center;justify-content:center;
                                   color:${d.dark_base || '#18061F'};font-size:28px;font-weight:700;
                                   font-family:Georgia,serif;">α</div>`
                }
                <div style="flex:1;min-width:0;">
                    <div style="font-size:11px;letter-spacing:0.12em;text-transform:uppercase;
                                color:${d.accent || '#D9A54A'};font-weight:600;">
                        ${d.company || __("Your Company")}
                    </div>
                    <div style="font-size:22px;font-weight:700;margin-top:4px;color:${d.text_on_dark || '#F5EDEF'};">
                        ${frappe.utils.escape_html(display_name)}
                    </div>
                    ${d.tagline
                        ? `<div style="font-size:13px;color:${d.text_on_dark_muted || '#E6D6BE'};
                                       margin-top:2px;opacity:0.95;">${frappe.utils.escape_html(d.tagline)}</div>`
                        : ''
                    }
                </div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                    <span style="background:${d.primary || '#7A2F87'};color:#FFF;
                                 padding:8px 16px;border-radius:8px;font-size:12.5px;font-weight:500;">
                        ${__("Top Up")}
                    </span>
                    <span style="background:${d.accent || '#D9A54A'};color:${d.dark_base || '#18061F'};
                                 padding:8px 16px;border-radius:8px;font-size:12.5px;font-weight:500;">
                        ${__("Book Now")}
                    </span>
                </div>
            </div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:8px;margin-top:10px;">
            ${swatch_row("Primary", d.primary, d.primary_dark, d.primary_light)}
            ${swatch_row("Accent", d.accent, d.accent_light)}
            ${swatch_row("Pink", d.pink, d.pink_dark)}
            ${swatch_row("Dark", d.dark_base, d.dark_mid, d.dark_elev)}
        </div>
    `;
    frm.get_field("preview_html").$wrapper.html(html);

    // Also render the palette HTML preview lower down in the form
    frm.get_field("palette_html_preview").$wrapper.html(palette_grid_html(d));
}

function swatch_row(label, ...colors) {
    return `
        <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:8px 10px;">
            <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.05em;
                        color:#6B7280;font-weight:600;margin-bottom:6px;">${label}</div>
            <div style="display:flex;gap:4px;">
                ${colors.filter(c => c).map(c => `
                    <div title="${c}" style="flex:1;height:20px;border-radius:4px;background:${c};
                                              border:1px solid rgba(0,0,0,0.08);"></div>
                `).join('')}
            </div>
        </div>
    `;
}

function palette_grid_html(d) {
    const sw = (label, color, on_dark = false) => `
        <div style="display:flex;align-items:center;gap:10px;padding:6px 0;">
            <div style="width:32px;height:32px;border-radius:6px;background:${color || '#FFF'};
                        border:1px solid rgba(0,0,0,0.1);
                        ${on_dark ? 'box-shadow:inset 0 0 0 1px rgba(255,255,255,0.15);' : ''}"></div>
            <div style="flex:1;">
                <div style="font-size:12px;font-weight:600;color:#374151;">${label}</div>
                <div style="font-size:11px;color:#9CA3AF;font-family:monospace;">${color || '—'}</div>
            </div>
        </div>
    `;
    return `
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
                    gap:0 16px;padding:8px 0;">
            <div>
                <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.06em;
                            color:#6B7280;font-weight:700;margin-bottom:4px;">${__("Brand")}</div>
                ${sw("Primary", d.primary)}
                ${sw("Primary Dark", d.primary_dark)}
                ${sw("Primary Light", d.primary_light)}
                ${sw("Primary Soft", d.primary_soft)}
            </div>
            <div>
                <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.06em;
                            color:#6B7280;font-weight:700;margin-bottom:4px;">${__("Accents")}</div>
                ${sw("Accent (Gold)", d.accent)}
                ${sw("Accent Light", d.accent_light)}
                ${sw("Pink / Active", d.pink)}
                ${sw("Pink Dark", d.pink_dark)}
            </div>
            <div>
                <div style="font-size:10px;text-transform:uppercase;letter-spacing:0.06em;
                            color:#6B7280;font-weight:700;margin-bottom:4px;">${__("Dark Surfaces")}</div>
                ${sw("Dark Base", d.dark_base, true)}
                ${sw("Dark Mid", d.dark_mid, true)}
                ${sw("Dark Elevated", d.dark_elev, true)}
            </div>
        </div>
    `;
}

function render_logo_preview(frm) {
    const d = frm.doc;
    if (!d.logo && !d.logo_on_dark && !d.favicon) {
        frm.get_field("logo_preview_html").$wrapper.html("");
        return;
    }
    const block = (label, src, bg) => src ? `
        <div style="text-align:center;flex:1;">
            <div style="font-size:11px;color:#6B7280;margin-bottom:6px;
                        text-transform:uppercase;letter-spacing:0.04em;">${label}</div>
            <div style="background:${bg};border-radius:8px;padding:14px;display:flex;
                        align-items:center;justify-content:center;min-height:80px;">
                <img src="${src}" style="max-height:60px;max-width:100%;border-radius:4px;"/>
            </div>
        </div>
    ` : '';
    frm.get_field("logo_preview_html").$wrapper.html(`
        <div style="display:flex;gap:12px;align-items:stretch;">
            ${block(__("Logo (light bg)"), d.logo, '#F9FAFB')}
            ${block(__("Logo (dark bg)"), d.logo_on_dark, '#18061F')}
            ${block(__("Favicon"), d.favicon, '#F9FAFB')}
        </div>
    `);
}
