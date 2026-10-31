// S4 - DEVONthink 3 scripting probe (JXA). Run with:
//   osascript -l JavaScript probe.js info
//   osascript -l JavaScript probe.js selftest <SpikeDatabaseName> <fixturesDir> [<SecondSpikeDatabaseName>]
//   osascript -l JavaScript probe.js read <uuid>
// Every command name below is UNVERIFIED for DT3 3.9.17 until this probe runs: each check records
// either its value or the exact error, and both are evidence. Arguments come only via argv.
// Writes only inside databases whose name contains "Spike". Never deletes anything.
ObjC.import('Foundation');

const DT3_ID = 'com.devon-technologies.think3';

function dt3() {
    const app = Application(DT3_ID);
    app.includeStandardAdditions = false;
    return app;
}

function check(results, name, fn) {
    try {
        const v = fn();
        results.push({ check: name, ok: true, value: v === undefined ? null : v });
    } catch (e) {
        results.push({ check: name, ok: false, error: String(e) });
    }
}

function describe(r) {
    const out = {};
    const props = ['uuid', 'name', 'type', 'kind', 'referenceURL', 'tags', 'comment', 'location',
        'creationDate', 'modificationDate', 'additionDate', 'size', 'wordCount', 'contentHash',
        'numberOfDuplicates', 'numberOfReplicants', 'customMetaData', 'path', 'filename'];
    props.forEach(function (p) {
        try { const v = r[p](); out[p] = (v instanceof Date) ? v.toISOString() : v; }
        catch (e) { out[p] = 'ERR: ' + String(e); }
    });
    try { out.plainTextStart = String(r.plainText()).slice(0, 120); } catch (e) { out.plainTextStart = 'ERR: ' + String(e); }
    try { out.database = r.database().name(); } catch (e) { out.database = 'ERR: ' + String(e); }
    return out;
}

function info() {
    const results = [];
    check(results, 'version', function () { return dt3().version(); });
    check(results, 'name', function () { return dt3().name(); });
    check(results, 'id', function () { return dt3().id(); });
    check(results, 'isDT3', function () { return String(dt3().version()).indexOf('3.') === 0; });
    check(results, 'databases', function () { return dt3().databases().map(function (d) { return d.name(); }); });
    return results;
}

function selftest(dbName, fixtures, db2Name) {
    if (!dbName || dbName.indexOf('Spike') < 0) throw new Error('Refusing: database name must contain "Spike"');
    const app = dt3();
    const results = [];
    const db = app.databases.whose({ name: dbName })()[0];
    if (!db) throw new Error('Database not open: ' + dbName);
    const stamp = new Date().toISOString().replace(/[:.]/g, '-');
    let group, target, other, md, txt, pdf, ocrRec;

    check(results, 'createLocation group', function () { group = app.createLocation('/_spike/' + stamp, { in: db }); return group.uuid(); });
    check(results, 'createLocation target', function () { target = app.createLocation('/_spike/' + stamp + '/target', { in: db }); return target.uuid(); });
    check(results, 'createLocation other', function () { other = app.createLocation('/_spike/' + stamp + '/other', { in: db }); return other.uuid(); });

    check(results, 'create markdown via content', function () {
        md = app.createRecordWith({ name: 'spike-md-content', type: 'markdown', content: '# Spike\n\nGrüezi Zürich' }, { in: group });
        return describe(md);
    });
    check(results, 'create markdown via plainText', function () {
        return describe(app.createRecordWith({ name: 'spike-md-plaintext', type: 'markdown', plainText: '# Spike\n\nGrüezi Zürich' }, { in: group }));
    });
    check(results, 'create txt via plainText (run 2: stays empty)', function () {
        return describe(app.createRecordWith({ name: 'spike-txt-plaintext', type: 'txt', plainText: 'Spike text record äöü éèà' }, { in: group }));
    });
    check(results, 'create txt via content', function () {
        txt = app.createRecordWith({ name: 'spike-txt', type: 'txt', content: 'Spike text record äöü éèà ' + stamp }, { in: group });
        return describe(txt);
    });

    check(results, 'getRecordWithUuid roundtrip', function () { return app.getRecordWithUuid(txt.uuid()).name(); });

    check(results, 'undo-journal read: name/tags/comment before change', function () {
        return { name: txt.name(), tags: txt.tags(), comment: txt.comment() };
    });
    check(results, 'set name/tags/comment', function () {
        txt.name = '20260417000000_Muster-Treuhand-AG_Erika-Beispiel_Spike';
        txt.tags = ['spike', 'invoice'];
        txt.comment = 'Line 1\nLine 2\nLine 3';
        return { name: txt.name(), tags: txt.tags(), comment: txt.comment() };
    });

    check(results, 'addCustomMetaData text', function () { return app.addCustomMetaData('rule', { for: 'spikesource', to: txt }); });
    check(results, 'addCustomMetaData date', function () { return app.addCustomMetaData(new Date(Date.UTC(2026, 3, 17)), { for: 'spikedate', to: txt }); });
    check(results, 'getCustomMetaData', function () { return app.getCustomMetaData({ for: 'spikesource', from: txt }); });
    check(results, 'customMetaData dict', function () { return txt.customMetaData(); });

    check(results, 'replicate to other group', function () {
        const r = app.replicate({ record: txt, to: other });
        return { result: r ? r.uuid() : null, sameUuid: r ? r.uuid() === txt.uuid() : null, replicants: txt.numberOfReplicants() };
    });
    check(results, 'duplicate in same database', function () {
        const d = app.duplicate({ record: txt, to: target });
        return { uuid: d.uuid(), differentUuid: d.uuid() !== txt.uuid(), duplicatesOfOriginal: txt.numberOfDuplicates() };
    });
    check(results, 'duplicates() list after 3 s', function () {
        delay(3);
        return { list: txt.duplicates().map(function (r) { return r.uuid(); }), numberOfDuplicates: txt.numberOfDuplicates() };
    });
    check(results, 'same text created twice -> duplicates?', function () {
        const body = 'Identical body for duplicate detection ' + stamp;
        const a = app.createRecordWith({ name: 'spike-dup-a', type: 'txt', content: body }, { in: group });
        const b = app.createRecordWith({ name: 'spike-dup-b', type: 'txt', content: body }, { in: group });
        delay(3);
        return { aHash: a.contentHash(), bHash: b.contentHash(), aDuplicates: a.numberOfDuplicates(),
                 aList: a.duplicates().map(function (r) { return r.uuid(); }), bUuid: b.uuid() };
    });
    check(results, 'move to target', function () { const m = app.move({ record: md, to: target }); return m.location(); });

    if (db2Name) {
        check(results, 'duplicate to second database', function () {
            if (db2Name.indexOf('Spike') < 0) throw new Error('second database name must contain "Spike"');
            const db2 = app.databases.whose({ name: db2Name })()[0];
            const g2 = app.createLocation('/_spike/' + stamp, { in: db2 });
            const d = app.duplicate({ record: txt, to: g2 });
            return { uuid: d.uuid(), database: d.database().name() };
        });
    }

    check(results, 'item link of original', function () { return txt.referenceURL(); });
    check(results, 'link note (markdown with item link)', function () {
        const n = app.createRecordWith({ name: 'spike-link-note', type: 'markdown',
            content: '# Link\n\n[Original](' + txt.referenceURL() + ')' }, { in: other });
        return describe(n);
    });

    const due = new Date(Date.now() + 86400000);
    check(results, 'reminder A: set property to app.Reminder()', function () {
        txt.reminder = app.Reminder({ schedule: 'once', dueDate: due, alarm: 'notification' });
        return 'set';
    });
    check(results, 'reminder B: make at record.reminder', function () {
        return String(app.make({ new: 'reminder', withProperties: { schedule: 'once', dueDate: due, alarm: 'notification' }, at: md.reminder }));
    });
    check(results, 'reminder read', function () { const r = txt.reminder(); return r ? { schedule: r.schedule(), due: r.dueDate().toISOString(), alarm: r.alarm() } : null; });

    check(results, 'import qrbill PDF', function () {
        pdf = app.import(fixtures + '/qrbill-qrr.pdf', { to: group });
        return describe(pdf);
    });
    check(results, 'import image-only PDF (no text layer expected)', function () {
        ocrRec = app.import(fixtures + '/ocr-de.pdf', { to: group });
        return describe(ocrRec);
    });
    check(results, 'ocr A: file + to', function () {
        const r = app.ocr({ file: fixtures + '/ocr-de.pdf', to: group });
        return r ? describe(r) : null;
    });
    check(results, 'ocr B: direct path + to', function () {
        const r = app.ocr(fixtures + '/ocr-fr.pdf', { to: group });
        return r ? describe(r) : null;
    });
    check(results, 'convertImage (OCR an existing record)', function () {
        const r = app.convertImage({ record: ocrRec, to: group });
        return r ? describe(r) : null;
    });
    return results;
}

function read(uuid) {
    const r = dt3().getRecordWithUuid(uuid);
    if (!r) throw new Error('no record');
    return { name: r.name(), tags: r.tags() };
}

function run(argv) {
    const cmd = argv[0];
    let out;
    if (cmd === 'info') out = info();
    else if (cmd === 'selftest') out = selftest(argv[1], argv[2], argv[3]);
    else if (cmd === 'read') out = read(argv[1]);
    else throw new Error('usage: info | selftest <SpikeDB> <fixturesDir> [<SpikeDB2>] | read <uuid>');
    return JSON.stringify(out, null, 1);
}
