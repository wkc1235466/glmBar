use tiny_skia::{Color, Paint, PathBuilder, Pixmap, Stroke, Transform};

/// Create a tray icon PNG showing usage percentage as a colored arc.
pub fn create_usage_icon(percent: Option<f64>) -> Vec<u8> {
    let size = 64u32;
    let mut pixmap = Pixmap::new(size, size).unwrap();

    let center = (size as f32) / 2.0;
    let radius = (size as f32) / 2.0 - 8.0;

    // Background circle (dark gray ring)
    let mut bg_paint = Paint::default();
    bg_paint.set_color(Color::from_rgba8(60, 60, 60, 255));
    bg_paint.anti_alias = true;

    let mut stroke = Stroke::default();
    stroke.width = 4.0;

    if let Some(path) = create_circle_path(center, center, radius) {
        pixmap.stroke_path(&path, &bg_paint, &stroke, Transform::identity(), None);
    }

    match percent {
        Some(pct) => {
            // Usage arc
            let color = if pct < 50.0 {
                Color::from_rgba8(76, 175, 80, 255) // green
            } else if pct < 80.0 {
                Color::from_rgba8(255, 193, 7, 255) // yellow
            } else {
                Color::from_rgba8(244, 67, 54, 255) // red
            };

            let mut arc_paint = Paint::default();
            arc_paint.set_color(color);
            arc_paint.anti_alias = true;

            let end_angle = (pct / 100.0) * 360.0; // f64
            let end_angle_f32 = end_angle as f32;
            if let Some(path) = create_arc_path(center, center, radius, -90.0, -90.0 + end_angle_f32) {
                pixmap.stroke_path(&path, &arc_paint, &stroke, Transform::identity(), None);
            }

            // Draw percentage text using simple pixel patterns
            let text = format!("{:.0}", pct);
            draw_simple_text(&mut pixmap, center, &text, color);
        }
        None => {
            // Error state: question mark
            draw_question_mark(&mut pixmap, center);
        }
    }

    pixmap.encode_png().unwrap_or_default()
}

fn create_circle_path(cx: f32, cy: f32, r: f32) -> Option<tiny_skia::Path> {
    let mut pb = PathBuilder::new();
    let c = r * 0.552284749831;
    pb.move_to(cx + r, cy);
    pb.cubic_to(cx + r, cy + c, cx + c, cy + r, cx, cy + r);
    pb.cubic_to(cx - c, cy + r, cx - r, cy + c, cx - r, cy);
    pb.cubic_to(cx - r, cy - c, cx - c, cy - r, cx, cy - r);
    pb.cubic_to(cx + c, cy - r, cx + r, cy - c, cx + r, cy);
    pb.close();
    pb.finish()
}

fn create_arc_path(cx: f32, cy: f32, r: f32, start_deg: f32, end_deg: f32) -> Option<tiny_skia::Path> {
    let mut pb = PathBuilder::new();

    let start_rad = start_deg.to_radians();
    let end_rad = end_deg.to_radians();

    let x0 = cx + r * start_rad.cos();
    let y0 = cy + r * start_rad.sin();
    pb.move_to(x0, y0);

    let segments = ((end_deg - start_deg).abs() / 5.0).ceil() as i32;
    let step = (end_rad - start_rad) / segments.max(1) as f32;

    for i in 1..=segments {
        let angle = start_rad + step * i as f32;
        let x = cx + r * angle.cos();
        let y = cy + r * angle.sin();
        pb.line_to(x, y);
    }

    pb.finish()
}

/// Simple 3x5 pixel font for digits 0-9 and %
const DIGIT_PATTERNS: [&[u8]; 10] = [
    // 0
    &[0b111, 0b101, 0b101, 0b101, 0b111],
    // 1
    &[0b010, 0b110, 0b010, 0b010, 0b111],
    // 2
    &[0b111, 0b001, 0b111, 0b100, 0b111],
    // 3
    &[0b111, 0b001, 0b111, 0b001, 0b111],
    // 4
    &[0b101, 0b101, 0b111, 0b001, 0b001],
    // 5
    &[0b111, 0b100, 0b111, 0b001, 0b111],
    // 6
    &[0b111, 0b100, 0b111, 0b101, 0b111],
    // 7
    &[0b111, 0b001, 0b010, 0b010, 0b010],
    // 8
    &[0b111, 0b101, 0b111, 0b101, 0b111],
    // 9
    &[0b111, 0b101, 0b111, 0b001, 0b111],
];

const PERCENT_PATTERN: &[u8] = &[0b101, 0b001, 0b010, 0b100, 0b101];

fn draw_simple_text(pixmap: &mut Pixmap, center: f32, text: &str, color: Color) {
    let chars: Vec<char> = text.chars().collect();
    let char_width = 4u32; // 3 pixels + 1 spacing
    let total_width = chars.len() as u32 * char_width;
    let start_x = center as u32 - total_width / 2;
    let start_y = center as u32 - 3; // 5 pixels tall, center vertically

    let r = (color.red() * 255.0) as u8;
    let g = (color.green() * 255.0) as u8;
    let b = (color.blue() * 255.0) as u8;
    let a = (color.alpha() * 255.0) as u8;

    let w = pixmap.width();

    for (i, ch) in chars.iter().enumerate() {
        let pattern = if ch.is_ascii_digit() {
            DIGIT_PATTERNS[ch.to_digit(10).unwrap() as usize]
        } else if *ch == '%' {
            PERCENT_PATTERN
        } else {
            continue;
        };

        let offset_x = start_x + (i as u32) * char_width;

        for (row, &bits) in pattern.iter().enumerate() {
            for col in 0..3 {
                if bits & (1 << (2 - col)) != 0 {
                    let px = offset_x + col as u32;
                    let py = start_y + row as u32;
                    if px < pixmap.width() && py < pixmap.height() {
                        let idx = ((py * w + px) * 4) as usize;
                        let data = pixmap.data_mut();
                        data[idx] = r;
                        data[idx + 1] = g;
                        data[idx + 2] = b;
                        data[idx + 3] = a;
                    }
                }
            }
        }
    }
}

fn draw_question_mark(pixmap: &mut Pixmap, center: f32) {
    // Simple "?" using pixel pattern
    let pattern: &[u8] = &[0b111, 0b001, 0b111, 0b000, 0b010];

    let r = 120u8;
    let g = 120u8;
    let b = 120u8;

    let start_x = center as u32 - 1;
    let start_y = center as u32 - 2;

    let w = pixmap.width();

    for (row, &bits) in pattern.iter().enumerate() {
        for col in 0..3 {
            if bits & (1 << (2 - col)) != 0 {
                let px = start_x + col as u32;
                let py = start_y + row as u32;
                if px < pixmap.width() && py < pixmap.height() {
                    let idx = ((py * w + px) * 4) as usize;
                    let data = pixmap.data_mut();
                    data[idx] = r;
                    data[idx + 1] = g;
                    data[idx + 2] = b;
                    data[idx + 3] = 255;
                }
            }
        }
    }
}
