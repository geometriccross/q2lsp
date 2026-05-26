import * as path from 'path';

export const isAbsolutePath = (value: string): boolean => {
	return path.isAbsolute(value);
};
