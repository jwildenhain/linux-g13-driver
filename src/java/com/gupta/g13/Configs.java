package com.gupta.g13;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.Date;
import java.util.Properties;

public class Configs {

	public static final String [][] defaultBindings = {
		{"G34", "10"},         {"G29", "59"}, {"G30", "60"}, {"G31", "61"}, {"G32", "62"},        {"G35", "11"},
		{"G0" , "3" }, {"G1" , "4" }, {"G2",  "5" }, {"G3",  "6" }, {"G4",  "7" }, {"G5",  "8" }, {"G6",  "9" },
			{"G7" , "16"}, {"G8" , "17"}, {"G9",  "18"}, {"G10", "19"}, {"G11", "20"}, {"G12", "21"}, {"G13", "22"},
				{"G14", "30"}, {"G15", "31"}, {"G16", "32"}, {"G17", "33"}, {"G18", "34"},
					{"G19", "44"}, {"G20", "45"}, {"G21", "46"},
					/* Stick Buttons */ {"G22", "57"}, {"G23", "58"},
					/* Stick */ {"G36" , "103"}, {"G37" , "105"}, {"G38",  "106"}, {"G39", "108"},
	};

	public static final String [][] defaultMacros = {
		{"CTRL-ALT-DEL", "kd.29,kd.56,kd.111,d.20,ku.111,ku.56,ku.29,d.100"},
		{"ALT-TAB", "kd.56,kd.15,d.20,ku.15,ku.56,d.100"},
		{"SHIFT-ALT-TAB", "kd.42,kd.56,kd.15,d.20,ku.15,ku.56,ku.42,d.100"},
		{"ALT-F1", "kd.56,kd.59,d.20,ku.59,ku.56,d.100"},
		{"ALT-F2", "kd.56,kd.60,d.20,ku.60,ku.56,d.100"},
		{"ALT-F3", "kd.56,kd.61,d.20,ku.61,ku.56,d.100"},
		{"ALT-F4", "kd.56,kd.62,d.20,ku.62,ku.56,d.100"},
		{"ALT-F5", "kd.56,kd.63,d.20,ku.63,ku.56,d.100"},
		{"ALT-F6", "kd.56,kd.64,d.20,ku.64,ku.56,d.100"},
		{"ALT-F7", "kd.56,kd.65,d.20,ku.65,ku.56,d.100"},
		{"ALT-F8", "kd.56,kd.66,d.20,ku.66,ku.56,d.100"},
		{"ALT-F9", "kd.56,kd.67,d.20,ku.67,ku.56,d.100"},
		{"ALT-F10", "kd.56,kd.68,d.20,ku.68,ku.56,d.100"},
		{"ALT-F11", "kd.56,kd.87,d.20,ku.87,ku.56,d.100"},
		{"ALT-F12", "kd.56,kd.88,d.20,ku.88,ku.56,d.100"},
		{"Print Screen", "kd.99,d.20,ku.99,d.100"},
		{"ALT-Print Screen", "kd.56,kd.99,d.20,ku.99,ku.56,d.100"},
		{"CTRL-Print Screen", "kd.29,kd.99,d.20,ku.99,ku.29,d.100"},
		{"Pause", "kd.119,d.20,ku.119,d.100"},
	};

	public static Properties loadBindings(int item) throws IOException {

	final String home = System.getenv("HOME").endsWith("/")?System.getenv("HOME"):System.getenv("HOME")+"/";
	final File file = new File(home + ".g13/bindings-" + item + ".properties");

	if (file.exists() == false) { // create new file
		if (file.getParentFile().exists() == false) {
			file.getParentFile().mkdirs();
		}

                final Properties props = new Properties();
                props.put("color", "255,255,255");
                props.put("lcd_mode", "logiframe");
                props.put("mod", "0");
                props.put("lcd_logiframe_page_count", "4");
                props.put("lcd_logiframe_page1_cmd", "");
                final String steamCmd =
                        "if [ -z \"$STEAM_API_KEY\" ] || ( [ -z \"$STEAM_ID\" ] && [ -z \"$STEAM_STEAMID\" ] ); then "
                        + "printf 'Steam Friends\\nSet STEAM_API_KEY and STEAM_ID/STEAM_STEAMID env vars\\n'; "
                        + "exit 0; fi; "
                        + "if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then "
                        + "printf 'Steam Friends\\nInstall curl and jq\\n'; exit 0; fi; "
                        + "steam_id=\"${STEAM_ID:-${STEAM_STEAMID:-}}\"; "
                        + "friend_ids=$(curl -sf \"https://api.steampowered.com/ISteamUser/GetFriendList/v0001/?key=$STEAM_API_KEY&steamid=$steam_id&relationship=friend\" | jq -r '.friendslist.friends[]? | .steamid' | tr '\\n' ',' | sed 's/,$//'); "
                        + "if [ -z \"$friend_ids\" ]; then printf 'Steam Friends\\nNo friends found\\n'; exit 0; fi; "
                        + "online=$(curl -sf \"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key=$STEAM_API_KEY&steamids=$friend_ids\" | jq -r '.response.players[]? | select((.personastate // 0) > 0) | .personaname'); "
                        + "count=$(printf '%s\\n' \"$online\" | sed '/^$/d' | awk 'END {print NR}'); "
                        + "printf 'Steam Friends\\n'; if [ \"$count\" -eq 0 ]; then printf 'No friends online\\n'; exit 0; fi; "
                        + "printf 'Online: %s\\n' \"$count\"; printf '%s\\n' \"$online\" | head -n 3;";
                props.put("lcd_logiframe_page2_cmd", steamCmd);

                final String tokenCmd =
                        "if ! command -v curl >/dev/null 2>&1 || ! command -v jq >/dev/null 2>&1; then "
                        + "printf 'Token Usage\\nInstall curl and jq\\n'; exit 0; fi; "
                        + "today=$(date +%F); AG_USED=n/a; AG_LIMIT=n/a; "
                        + "if [ -n \"$ANTIGRAVITY_USAGE_URL\" ] && [ -n \"$ANTIGRAVITY_API_KEY\" ]; then "
                        + "ag=$(curl -sf --max-time 8 -H \"Authorization: Bearer $ANTIGRAVITY_API_KEY\" \"$ANTIGRAVITY_USAGE_URL\"); "
                        + "if [ -n \"$ag\" ]; then AG_USED=$(printf '%s' \"$ag\" | jq -r '.used // .tokens_used // .usage // \"n/a\"'); AG_LIMIT=$(printf '%s' \"$ag\" | jq -r '.daily_limit // .limit // \"n/a\"'); fi; fi; "
                        + "GEM_USED=n/a; GEM_LIMIT=n/a; "
                        + "if [ -n \"$GEMINI_USAGE_URL\" ] && [ -n \"$GEMINI_API_KEY\" ]; then "
                        + "gem=$(curl -sf --max-time 8 -H \"x-goog-api-key: $GEMINI_API_KEY\" \"$GEMINI_USAGE_URL\"); "
                        + "if [ -n \"$gem\" ]; then GEM_USED=$(printf '%s' \"$gem\" | jq -r '.used // .tokens_used // .usage // .total_tokens // \"n/a\"'); GEM_LIMIT=$(printf '%s' \"$gem\" | jq -r '.daily_limit // .limit // \"n/a\"'); fi; fi; "
                        + "CX_USED=n/a; CX_LIMIT=n/a; "
                        + "if [ -n \"$OPENAI_API_KEY\" ]; then "
                        + "openai_usage=$(curl -sf --max-time 8 -H \"Authorization: Bearer $OPENAI_API_KEY\" \"https://api.openai.com/v1/dashboard/billing/usage?start_date=$today&end_date=$today\"); "
                        + "openai_sub=$(curl -sf --max-time 8 -H \"Authorization: Bearer $OPENAI_API_KEY\" \"https://api.openai.com/v1/dashboard/billing/subscription\"); "
                        + "if [ -n \"$openai_usage\" ]; then CX_USED=$(printf '%s' \"$openai_usage\" | jq -r '.total_usage // .total_tokens // .usage.total_tokens // \"n/a\"'); fi; "
                        + "if [ -n \"$openai_sub\" ]; then CX_LIMIT=$(printf '%s' \"$openai_sub\" | jq -r '.hard_limit_usd // \"n/a\"'); fi; fi; "
                        + "printf 'Token Usage\\n'; printf 'Antigravity: %s/%s\\n' \"$AG_USED\" \"$AG_LIMIT\"; "
                        + "printf 'Gemini: %s/%s\\n' \"$GEM_USED\" \"$GEM_LIMIT\"; "
                        + "printf 'Codex/GPT: %s/%s\\n' \"$CX_USED\" \"$CX_LIMIT\";";
                props.put("lcd_logiframe_page3_cmd", tokenCmd);
                props.put("lcd_logiframe_page4_cmd", "");
                props.put("lcd_logiframe_page1_color", "0,128,255");
                props.put("lcd_logiframe_page2_color", "255,153,0");
                props.put("lcd_logiframe_page3_color", "0,200,64");
                props.put("lcd_logiframe_page4_color", "255,64,64");

		for (final String [] binding: defaultBindings) {
			props.put(binding[0], "p,k." + binding[1]);
		}

		saveBindings(item, props);

		return props;
	}

	final Properties props = new Properties();
	final FileInputStream fis = new FileInputStream(file);
	props.load(fis);

	return props;
	}


	public static void saveBindings(int item, Properties props) throws IOException {
	final String home = System.getenv("HOME").endsWith("/")?System.getenv("HOME"):System.getenv("HOME")+"/";
	final File file = new File(home + ".g13/bindings-" + item + ".properties");
	if (file.exists()) {
		file.delete();
	}

	final FileOutputStream fos = new FileOutputStream(file);
	props.store(fos, new Date().toString());
	}

	public static Properties loadMacro(int macroNum) throws IOException {
	final String home = System.getenv("HOME").endsWith("/")?System.getenv("HOME"):System.getenv("HOME")+"/";
	final File file = new File(home + ".g13/macro-" + macroNum + ".properties");

	if (file.exists() == false) { // create new file
		if (file.getParentFile().exists() == false) {
			file.getParentFile().mkdirs();
		}

		final Properties props = new Properties();

		/*
		if (JavaToLinuxKeymapping.linuxToJavaCodes.length > macroNum && 
			((String)JavaToLinuxKeymapping.linuxToJavaCodes[macroNum][0]).length() > 0) {

			props.put("name", (String)JavaToLinuxKeymapping.linuxToJavaCodes[macroNum][0]);
			int keycode = (Integer)JavaToLinuxKeymapping.linuxToJavaCodes[macroNum][1];
			String seq = "kd." + keycode + ",ku." + keycode + ",d.100";
			props.put("sequence", seq);
		}
		else {
			props.put("name", "");
			props.put("sequence", "");
		}
		*/

		if (macroNum < defaultMacros.length) {
			props.put("name", defaultMacros[macroNum][0]);
			props.put("sequence", defaultMacros[macroNum][1]);
		}
		else {
			props.put("name", "");
			props.put("sequence", "");
		}
		props.put("id", Integer.toString(macroNum));
		saveMacro(macroNum, props);

		return props;
	}

	final Properties props = new Properties();
	final FileInputStream fis = new FileInputStream(file);
	props.load(fis);

	props.put("id", Integer.toString(macroNum));

	return props;
	}

	public static void saveMacro(int macroNum, Properties props) throws IOException {
	final String home = System.getenv("HOME").endsWith("/")?System.getenv("HOME"):System.getenv("HOME")+"/";
	final File file = new File(home + ".g13/macro-" + macroNum + ".properties");
	if (file.exists()) {
		file.delete();
	}

	final FileOutputStream fos = new FileOutputStream(file);
	props.store(fos, new Date().toString());

	}

}
