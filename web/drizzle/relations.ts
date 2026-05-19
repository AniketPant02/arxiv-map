import { relations } from "drizzle-orm/relations";
import { arxivPapers, paperAuthors, paperAuthorInstitutions, institutions, arxivPaperCategories } from "./schema";

export const paperAuthorsRelations = relations(paperAuthors, ({one, many}) => ({
	arxivPaper: one(arxivPapers, {
		fields: [paperAuthors.arxivId],
		references: [arxivPapers.arxivId]
	}),
	paperAuthorInstitutions: many(paperAuthorInstitutions),
}));

export const arxivPapersRelations = relations(arxivPapers, ({many}) => ({
	paperAuthors: many(paperAuthors),
	arxivPaperCategories: many(arxivPaperCategories),
}));

export const paperAuthorInstitutionsRelations = relations(paperAuthorInstitutions, ({one}) => ({
	paperAuthor: one(paperAuthors, {
		fields: [paperAuthorInstitutions.paperAuthorId],
		references: [paperAuthors.id]
	}),
	institution: one(institutions, {
		fields: [paperAuthorInstitutions.institutionId],
		references: [institutions.id]
	}),
}));

export const institutionsRelations = relations(institutions, ({many}) => ({
	paperAuthorInstitutions: many(paperAuthorInstitutions),
}));

export const arxivPaperCategoriesRelations = relations(arxivPaperCategories, ({one}) => ({
	arxivPaper: one(arxivPapers, {
		fields: [arxivPaperCategories.arxivId],
		references: [arxivPapers.arxivId]
	}),
}));