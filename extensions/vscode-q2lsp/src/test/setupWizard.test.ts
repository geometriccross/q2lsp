import * as assert from 'assert';
import { SETUP_WIZARD_ACTIONS, buildSetupWizardHtml } from '../setupWizard';

suite('q2lsp setup wizard tests', () => {
	test('wizard html shows the setup actions', () => {
		const html = buildSetupWizardHtml({ nonce: 'test-nonce' });

		for (const action of SETUP_WIZARD_ACTIONS) {
			assert.ok(html.includes(action.label));
			assert.ok(html.includes(action.command));
		}
	});
});
