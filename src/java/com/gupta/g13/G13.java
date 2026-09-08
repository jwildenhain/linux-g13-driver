package com.gupta.g13;

import java.awt.BorderLayout;
import java.awt.Dimension;
import java.awt.FlowLayout;
import java.awt.Toolkit;
import java.util.Properties;
import java.util.StringTokenizer;

import javax.swing.BoxLayout;
import javax.swing.BorderFactory;
import javax.swing.JComboBox;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;

/**
 * @author jgupta
 *
 */
public class G13 extends JPanel {

	private static final long serialVersionUID = 1L;

	public static final String VERSION = G13.class.getPackage().getImplementationVersion()!=null?G13.class.getPackage().getImplementationVersion():"Unknown";

	private static final int MAX_MACROS = 200;

	private final ImageMap g13Label = new ImageMap();
	private final LogiFramePanel logiFramePanel = new LogiFramePanel();
	private final KeybindPanel keybindPanel = new KeybindPanel();
	private final MacroEditorPanel macroEditorPanel = new MacroEditorPanel();

	private final JComboBox profileSelection = new JComboBox();

	private Properties [] keyBindings = new Properties[4];

	private Properties [] macros = new Properties[MAX_MACROS];

	private boolean updatingProfile = false;

	public G13() {
		setLayout(new BorderLayout());

		try {
			for (int i = 0; i < keyBindings.length; i++) {
				keyBindings[i] = Configs.loadBindings(i);
			}

			for (int i = 0; i < macros.length; i++) {
				macros[i] = Configs.loadMacro(i);
			}

			for (int i = 0; i < 4; i++) {
				profileSelection.addItem("P" + (i + 1));
			}

			setProfile(0);
		}
		catch (Exception e) {
			e.printStackTrace();
			JOptionPane.showMessageDialog(this, e);
		}

		g13Label.addListener(new ImageMapListener() {
			@Override
			public void selected(Key key) {

				if (key == null) {
					keybindPanel.setSelectedKey(null);
					return;
				}

				if (key.getG13KeyCode() == 25 || key.getG13KeyCode() == 26 ||
						key.getG13KeyCode() == 27 || key.getG13KeyCode() == 28) {
					setProfile(key.getG13KeyCode() - 25);
					return;
				}

				keybindPanel.setSelectedKey(key);
			}

			@Override
			public void mouseover(Key key) {
			}
		});

		final JPanel p = new JPanel(new BorderLayout());
		p.setBorder(BorderFactory.createTitledBorder("G13 Keypad"));
		p.add(g13Label, BorderLayout.CENTER);
		add(p, BorderLayout.CENTER);

		final JPanel profilePanel = new JPanel(new FlowLayout(FlowLayout.LEFT));
		profilePanel.add(new JLabel("Profile"));
		profilePanel.add(profileSelection);

		profileSelection.addActionListener(e -> {
			if (updatingProfile) {
				return;
			}
			setProfile(profileSelection.getSelectedIndex());
		});

		final JPanel rightPanel = new JPanel(new BorderLayout());
		final JPanel controls = new JPanel();
		controls.setLayout(new BoxLayout(controls, BoxLayout.Y_AXIS));
		controls.setBorder(BorderFactory.createTitledBorder("Profile Controls"));
		controls.add(profilePanel);
		controls.add(logiFramePanel);
		controls.add(keybindPanel);
		controls.add(macroEditorPanel);
		rightPanel.add(controls, BorderLayout.NORTH);
		add(rightPanel, BorderLayout.EAST);

		keybindPanel.setMacros(macros);
		macroEditorPanel.setMacros(macros);
	}

	private void setProfile(final int profileNum) {
		if (profileNum < 0 || profileNum >= keyBindings.length) {
			return;
		}

		updatingProfile = true;
		profileSelection.setSelectedIndex(profileNum);
		updatingProfile = false;
		mapBindings(profileNum);
	}

	private void mapBindings(int bindingnum) {
		keybindPanel.setSelectedKey(null);
		keybindPanel.setBindings(bindingnum, keyBindings[bindingnum]);
		logiFramePanel.setBindings(bindingnum, keyBindings[bindingnum]);

		for (int i = 0; i < 40; i++) {
			String property = "G" + i;
			String val = keyBindings[bindingnum].getProperty(property);

			final Key k = Key.getKeyFor(i);
			if (k == null) {
				continue;
			}

			k.setMappedValue("Unknown");
			k.setRepeats("N/A");

			if (val == null || val.length() == 0) {
				continue;
			}

			final StringTokenizer st = new StringTokenizer(val, ",.");
			if (!st.hasMoreTokens()) {
				continue;
			}

			final String type = st.nextToken();
			if (type.equals("p")) {
				String first = st.hasMoreTokens() ? st.nextToken() : "";
				String keyCodeText = first;
				if ("k".equals(first) && st.hasMoreTokens()) {
					keyCodeText = st.nextToken();
				}
				if (keyCodeText.length() > 0) {
					try {
						final int keycode = Integer.valueOf(keyCodeText);
						k.setMappedValue(JavaToLinuxKeymapping.cKeyCodeToString(keycode));
					} catch (NumberFormatException e) {
						// keep Unknown
					}
				}
			}
			else if (type.equals("m")) {
				int macroNum = -1;
				if (st.hasMoreTokens()) {
					try {
						macroNum = Integer.valueOf(st.nextToken());
					} catch (NumberFormatException e) {
						macroNum = -1;
					}
				}
				boolean repeats = false;
				if (st.hasMoreTokens()) {
					try {
						repeats = Integer.valueOf(st.nextToken()) != 0;
					} catch (NumberFormatException e) {
						repeats = false;
					}
				}
				if (macroNum >= 0 && macroNum < macros.length) {
					final String macroName = macros[macroNum].getProperty("name");
					k.setMappedValue("Macro: " + macroName);
					k.setRepeats(repeats ? "Yes" : "No");
				}
				else {
					k.setMappedValue("Macro: Unknown");
					k.setRepeats(repeats ? "Yes" : "No");
				}
			}
			else {
				k.setMappedValue("Unknown (" + type + ")");
			}
		}
	}

	/**
	 * @param args
	 */
	public static void main(String[] args) {
		final JFrame frame = new JFrame("G13 Configuation Tool, Version " + VERSION);
		frame.setIconImage(ImageMap.G13_KEYPAD.getImage());
		frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);

		final G13 g13 = new G13();
		frame.getContentPane().add(g13, BorderLayout.CENTER);

		frame.pack();
		final Dimension appSize = frame.getPreferredSize();
		final Dimension screenSize = Toolkit.getDefaultToolkit().getScreenSize();

		final int insetX = (screenSize.width - appSize.width) / 2;
		final int insetY = (screenSize.height - appSize.height) / 2;
		frame.setLocation(insetX, insetY);

		frame.setVisible(true);
	}

}
