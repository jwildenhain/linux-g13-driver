package com.gupta.g13;

import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.FlowLayout;
import java.awt.GridLayout;
import java.awt.event.ActionEvent;
import java.awt.event.FocusAdapter;
import java.awt.event.FocusEvent;
import java.util.Properties;
import java.util.StringTokenizer;

import javax.swing.BorderFactory;
import javax.swing.JButton;
import javax.swing.JComboBox;
import javax.swing.JColorChooser;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JTextField;

public class LogiFramePanel extends JPanel {

	private static final long serialVersionUID = 1L;

	private static final String PAGE1_COLOR_KEY = "lcd_logiframe_page1_color";
	private static final String PAGE2_COLOR_KEY = "lcd_logiframe_page2_color";
	private static final String PAGE3_COLOR_KEY = "lcd_logiframe_page3_color";
	private static final String PAGE4_COLOR_KEY = "lcd_logiframe_page4_color";
	private static final String[] PAGE_COLOR_KEYS = {
		PAGE1_COLOR_KEY,
		PAGE2_COLOR_KEY,
		PAGE3_COLOR_KEY,
		PAGE4_COLOR_KEY,
	};
	private static final String PAGE1_KEY = "lcd_logiframe_page1_cmd";
	private static final String PAGE2_KEY = "lcd_logiframe_page2_cmd";
	private static final String PAGE3_KEY = "lcd_logiframe_page3_cmd";
	private static final String PAGE4_KEY = "lcd_logiframe_page4_cmd";
	private static final String[] PAGE_CMD_KEYS = {
		PAGE1_KEY,
		PAGE2_KEY,
		PAGE3_KEY,
		PAGE4_KEY,
	};
	private static final String[] PAGE_LABELS = {
		"G26 (Usage)",
		"G27 (Steam Friends)",
		"G28 (Token Usage)",
		"G29 (Custom)",
	};
	private static final int[][] FALLBACK_PAGE_COLORS = {
		{0, 128, 255},
		{255, 153, 0},
		{0, 200, 64},
		{255, 64, 64},
	};

	private final JComboBox<String> modeField = new JComboBox<String>(new String[] {"stats", "sys", "system", "default", "fifo", "logiframe"});
	private final JTextField lcdPathField = new JTextField();
	private final JTextField pageCountField = new JTextField();
	private final JTextField[] pageCmdFields = new JTextField[4];
	private final JButton[] pageColorButtons = new JButton[4];

	private Properties bindings = null;
	private int bindingsId = -1;
	private boolean loadingData = false;

	public LogiFramePanel() {
		setLayout(new BorderLayout());
		setBorder(BorderFactory.createTitledBorder("LogiFrame / LCD Settings"));

		JPanel top = new JPanel(new GridLayout(3, 2, 6, 6));
		top.add(new JLabel("lcd_mode (stats/fifo/logiframe):"));
		top.add(modeField);
		top.add(new JLabel("lcd_path (fifo):"));
		top.add(lcdPathField);
		top.add(new JLabel("lcd_logiframe_page_count:"));
		top.add(pageCountField);

		JPanel center = new JPanel(new GridLayout(4, 1, 6, 6));
		for (int i = 0; i < 4; i++) {
			final int idx = i;
			JPanel row = new JPanel(new BorderLayout(6, 6));
			row.setBorder(BorderFactory.createTitledBorder("Page " + (i + 1) + " / " + PAGE_LABELS[i]));
			JTextField command = new JTextField();
			pageCmdFields[i] = command;
			JButton colorButton = new JButton("Set Color");
			pageColorButtons[i] = colorButton;
			JPanel right = new JPanel(new FlowLayout(FlowLayout.RIGHT));
			right.add(colorButton);
			row.add(command, BorderLayout.CENTER);
			row.add(right, BorderLayout.EAST);
			center.add(row);

			addAutoSaveListener(command);
			colorButton.addActionListener(new java.awt.event.ActionListener() {
				public void actionPerformed(final ActionEvent ae) {
					changePageColor(idx);
				}
			});
		}

		add(top, BorderLayout.NORTH);
		add(center, BorderLayout.CENTER);

		modeField.addActionListener(ae -> saveBindings());
		lcdPathField.addActionListener(ae -> saveBindings());
		lcdPathField.addFocusListener(new FocusAdapter() {
			@Override
			public void focusLost(FocusEvent e) {
				saveBindings();
			}
		});
		pageCountField.addActionListener(ae -> saveBindings());
		pageCountField.addFocusListener(new FocusAdapter() {
			@Override
			public void focusLost(FocusEvent e) {
				saveBindings();
			}
		});
	}

	public void setBindings(final int bindingNum, final Properties bindings) {
		loadingData = true;
		this.bindings = bindings;
		this.bindingsId = bindingNum;

		modeField.setSelectedItem(bindings.getProperty("lcd_mode", "logiframe"));
		lcdPathField.setText(bindings.getProperty("lcd_path", ""));
		pageCountField.setText(bindings.getProperty("lcd_logiframe_page_count", "4"));

		for (int i = 0; i < 4; i++) {
			pageCmdFields[i].setText(bindings.getProperty(PAGE_CMD_KEYS[i], ""));
			setPageColorButton(i, bindings.getProperty(PAGE_COLOR_KEYS[i]));
		}

		loadingData = false;
	}

	public void setPageColorButton(final int index, final String property) {
		int[] color = parseColor(property, FALLBACK_PAGE_COLORS[index]);
		Color c = new Color(color[0], color[1], color[2]);
		pageColorButtons[index].setBackground(c);
	}

	private void addAutoSaveListener(final JTextField field) {
		field.addActionListener(ae -> saveBindings());
		field.addFocusListener(new FocusAdapter() {
			@Override
			public void focusLost(FocusEvent e) {
				saveBindings();
			}
		});
	}

	private void changePageColor(final int index) {
		if (bindings == null || loadingData) {
			return;
		}

		int[] color = parseColor(bindings.getProperty(PAGE_COLOR_KEYS[index]), FALLBACK_PAGE_COLORS[index]);
		final Color c = new Color(color[0], color[1], color[2]);
		final Color newColor = JColorChooser.showDialog(this, "Choose page color", c);
		if (newColor == null) {
			return;
		}

		bindings.setProperty(PAGE_COLOR_KEYS[index], newColor.getRed() + "," + newColor.getGreen() + "," + newColor.getBlue());
		pageColorButtons[index].setBackground(newColor);
		saveBindings();
	}

	private int[] parseColor(final String value, final int[] fallback) {
		if (value == null || value.length() == 0) {
			return fallback;
		}

		StringTokenizer st = new StringTokenizer(value, ",");
		if (st.countTokens() < 3) {
			return fallback;
		}

		try {
			int r = Integer.parseInt(st.nextToken().trim());
			int g = Integer.parseInt(st.nextToken().trim());
			int b = Integer.parseInt(st.nextToken().trim());
			if (r < 0 || r > 255 || g < 0 || g > 255 || b < 0 || b > 255) {
				return fallback;
			}
			return new int[] { r, g, b };
		}
		catch (NumberFormatException e) {
			return fallback;
		}
	}

	private void saveBindings() {
		if (loadingData || bindings == null) {
			return;
		}

		String mode = (String) modeField.getSelectedItem();
		bindings.setProperty("lcd_mode", (mode == null ? "stats" : mode.trim()));
		bindings.setProperty("lcd_path", lcdPathField.getText().trim());

		int pageCount = 4;
		try {
			pageCount = Integer.parseInt(pageCountField.getText().trim());
		}
		catch (NumberFormatException e) {
			pageCount = 4;
		}
		if (pageCount < 1) {
			pageCount = 1;
		}
		if (pageCount > 4) {
			pageCount = 4;
		}
		bindings.setProperty("lcd_logiframe_page_count", Integer.toString(pageCount));
		pageCountField.setText(Integer.toString(pageCount));

		for (int i = 0; i < 4; i++) {
			bindings.setProperty(PAGE_CMD_KEYS[i], pageCmdFields[i].getText().trim());
		}

		try {
			Configs.saveBindings(bindingsId, bindings);
		}
		catch (Exception e) {
			JOptionPane.showMessageDialog(this, e);
		}
	}
}
