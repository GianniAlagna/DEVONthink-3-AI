-- DT3 Agent: Smart Rule script ("Apply Script" > External). Hands the matching records to the engine
-- and returns at once: one tiny JSON file per record in the engine's spool folder (SPEC §4.6, brief §2.6).
-- Verified on DEVONthink 3.9.17 / macOS 11.7 (Phase 2 T1): DT3 must be restarted once after installing.
on performSmartRule(theRecords)
	set spool to (POSIX path of (path to application support from user domain)) & "DT3 Agent/spool/"
	tell application id "com.devon-technologies.think3"
		repeat with r in theRecords
			set u to uuid of r
			set f to open for access (POSIX file (spool & u & ".json")) with write permission
			set eof f to 0
			write ("{\"uuid\":\"" & u & "\"}") to f as «class utf8»
			close access f
		end repeat
	end tell
end performSmartRule
