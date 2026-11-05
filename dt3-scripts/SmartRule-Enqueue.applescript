-- DT3 Agent: Smart Rule script ("Apply Script" > External). Hands the matching records to the engine
-- and returns at once: one tiny JSON file per record in the engine's spool folder (SPEC §4.6, brief §2.6).
-- Verified on DEVONthink 3.9.17 / macOS 11.7 (Phase 2 T1): DT3 must be restarted once after installing.
-- Floor 2026-11-05: no spool file appeared. The file writes now run outside the "tell DEVONthink" block,
-- so they are not sent to DEVONthink as Apple events (UNVERIFIED cause; this is the safe form either way).
on performSmartRule(theRecords)
	set spool to (POSIX path of (path to application support from user domain)) & "DT3 Agent/spool/"
	set uuids to {}
	tell application id "com.devon-technologies.think3"
		repeat with r in theRecords
			set end of uuids to (uuid of r) as text
		end repeat
	end tell
	repeat with u in uuids
		set p to spool & (u as text) & ".json"
		set f to open for access (POSIX file p) with write permission
		try
			set eof f to 0
			write ("{\"uuid\":\"" & (u as text) & "\"}") to f as «class utf8»
		end try
		close access f
	end repeat
end performSmartRule
